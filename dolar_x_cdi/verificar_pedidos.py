#!/usr/bin/env python3
"""Permite qualquer pessoa pedir o documento "Dólar x CDI" por e-mail,
sem precisar de acesso ao GitHub (nem ao Claude).

Como funciona: alguém manda um e-mail para a caixa configurada (a mesma
usada pelo monitor de notícias) com uma das frases-gatilho no ASSUNTO
(ver TRIGGERS abaixo, ex.: "dólar x cdi"). Este script roda periodicamente
via GitHub Actions (ver .github/workflows/dolar_x_cdi_pedidos.yml), lê a
caixa de entrada (IMAP), gera o PDF com dados atuais do BCB e responde
por e-mail com o documento anexado — direto para quem pediu, em "Responder".

Não depende de ninguém ter conta no GitHub: só de saber o endereço de
e-mail e escrever o assunto certo.
"""
from __future__ import annotations

import email
import imaplib
import os
import re
import smtplib
import sys
import traceback
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import decode_header
from email.utils import parseaddr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

IMAP_HOST = "imap.gmail.com"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

# Frases-gatilho aceitas no assunto do e-mail (case/acento-insensível).
# Precisa ser uma frase deliberada, pra não disparar em e-mails normais da caixa.
TRIGGERS = ["dolar x cdi", "dolar cdi", "gerar documento"]

MAX_PEDIDOS_POR_EXECUCAO = 5  # limite de segurança por execução do robô


def _normalizar(texto: str) -> str:
    import unicodedata
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return sem_acento.lower()


def _eh_pedido(assunto: str) -> bool:
    assunto_norm = _normalizar(assunto or "")
    return any(t in assunto_norm for t in TRIGGERS)


def _decodificar_header(valor: str) -> str:
    partes = decode_header(valor or "")
    saida = []
    for texto, cod in partes:
        if isinstance(texto, bytes):
            saida.append(texto.decode(cod or "utf-8", errors="replace"))
        else:
            saida.append(texto)
    return "".join(saida)


def _enviar_email(remetente_login: str, senha: str, destinatario: str, assunto: str,
                   corpo: str, anexo: Path | None = None) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"Dólar x CDI <{remetente_login}>"
    msg["To"] = destinatario
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    if anexo is not None:
        with anexo.open("rb") as f:
            parte = MIMEApplication(f.read(), _subtype="pdf")
        parte.add_header("Content-Disposition", "attachment", filename=anexo.name)
        msg.attach(parte)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(remetente_login, senha)
        smtp.sendmail(remetente_login, [destinatario], msg.as_string())


def main() -> int:
    usuario = os.environ.get("MAIL_USERNAME")
    senha = os.environ.get("MAIL_PASSWORD")
    if not usuario or not senha:
        print("MAIL_USERNAME / MAIL_PASSWORD não configurados — nada a fazer.")
        return 0

    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    imap.login(usuario, senha)
    imap.select("INBOX")

    status, dados = imap.search(None, "UNSEEN")
    if status != "OK":
        print("Falha ao buscar e-mails não lidos.")
        imap.logout()
        return 1

    ids = dados[0].split()
    pedidos = []
    for msg_id in ids:
        status, dados_msg = imap.fetch(msg_id, "(RFC822)")
        if status != "OK":
            continue
        msg = email.message_from_bytes(dados_msg[0][1])
        assunto = _decodificar_header(msg.get("Subject", ""))
        if not _eh_pedido(assunto):
            continue
        nome, endereco = parseaddr(msg.get("From", ""))
        if not endereco:
            continue
        pedidos.append((msg_id, assunto, endereco))
        # marca como lido imediatamente, pra não reprocessar em caso de erro adiante
        imap.store(msg_id, "+FLAGS", "\\Seen")

    imap.logout()

    if not pedidos:
        print("Nenhum pedido novo por e-mail.")
        return 0

    pedidos = pedidos[:MAX_PEDIDOS_POR_EXECUCAO]
    print(f"{len(pedidos)} pedido(s) novo(s) por e-mail.")

    from gerar_documento import gerar_a_partir_do_bcb  # import local: evita custo se não houver pedidos

    for msg_id, assunto, endereco in pedidos:
        print(f"Processando pedido de {endereco} (assunto: {assunto!r})...")
        try:
            caminho_pdf = gerar_a_partir_do_bcb(spread_aa=0.04)
            _enviar_email(
                usuario, senha, endereco,
                assunto="Dólar x CDI — documento gerado",
                corpo=(
                    "Olá!\n\n"
                    "Segue em anexo o documento \"Dólar x CDI\" atualizado, com dados oficiais "
                    "do Banco Central do Brasil (PTAX e CDI) para as janelas de 1, 5, 10 e 20 anos.\n\n"
                    "Esse e-mail foi gerado automaticamente a partir do seu pedido."
                ),
                anexo=caminho_pdf,
            )
            print(f"  -> respondido com sucesso para {endereco}.")
        except Exception:
            erro = traceback.format_exc()
            print(f"  -> ERRO ao gerar/enviar para {endereco}:\n{erro}")
            try:
                _enviar_email(
                    usuario, senha, endereco,
                    assunto="Dólar x CDI — não foi possível gerar o documento",
                    corpo=(
                        "Olá!\n\n"
                        "Recebemos seu pedido do documento \"Dólar x CDI\", mas houve um erro "
                        "ao gerá-lo agora. Avisamos o responsável para verificar — tente de novo "
                        "mais tarde ou fale com o Eduardo.\n"
                    ),
                )
            except Exception:
                print("  -> também falhou ao enviar o e-mail de erro para o solicitante.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
