from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "chave-secreta-fila"

DATABASE = "fila.db"


def conectar_banco():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def criar_banco():
    conn = conectar_banco()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            senha INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'aguardando',
            criado_em TEXT NOT NULL,
            iniciado_em TEXT,
            concluido_em TEXT
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def index():
    conn = conectar_banco()

    clientes = conn.execute("""
        SELECT *
        FROM clientes
        ORDER BY
            CASE
                WHEN status = 'aguardando' THEN 0
                WHEN status = 'em atendimento' THEN 1
                WHEN status = 'concluído' THEN 2
                WHEN status = 'cancelado' THEN 3
            END,
            id ASC
    """).fetchall()

    aguardando = conn.execute("""
        SELECT COUNT(*) AS total
        FROM clientes
        WHERE status = 'aguardando'
    """).fetchone()["total"]

    atendimento = conn.execute("""
        SELECT COUNT(*) AS total
        FROM clientes
        WHERE status = 'em atendimento'
    """).fetchone()["total"]

    concluidos = conn.execute("""
        SELECT COUNT(*) AS total
        FROM clientes
        WHERE status = 'concluído'
    """).fetchone()["total"]

    conn.close()

    return render_template(
        "index.html",
        clientes=clientes,
        aguardando=aguardando,
        atendimento=atendimento,
        concluidos=concluidos
    )


@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    nome = request.form.get("nome", "").strip()
    telefone = request.form.get("telefone", "").strip()

    if not nome:
        flash("Informe o nome do cliente.", "erro")
        return redirect(url_for("index"))

    conn = conectar_banco()

    # Gera a próxima senha em ordem crescente.
    resultado = conn.execute("""
        SELECT COALESCE(MAX(senha), 0) + 1 AS proxima_senha
        FROM clientes
    """).fetchone()

    senha = resultado["proxima_senha"]

    conn.execute("""
        INSERT INTO clientes
        (nome, telefone, senha, status, criado_em)
        VALUES (?, ?, ?, 'aguardando', ?)
    """, (
        nome,
        telefone,
        senha,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    flash(f"Cliente cadastrado. Senha: {senha}", "sucesso")

    return redirect(url_for("index"))


@app.route("/chamar-proximo", methods=["POST"])
def chamar_proximo():
    conn = conectar_banco()

    # Verifica se já existe alguém em atendimento.
    em_atendimento = conn.execute("""
        SELECT *
        FROM clientes
        WHERE status = 'em atendimento'
        LIMIT 1
    """).fetchone()

    if em_atendimento:
        flash(
            f"Finalize ou cancele o atendimento da senha "
            f"{em_atendimento['senha']} antes de chamar outra.",
            "erro"
        )
        conn.close()
        return redirect(url_for("index"))

    # FIFO: pega o cliente aguardando mais antigo.
    cliente = conn.execute("""
        SELECT *
        FROM clientes
        WHERE status = 'aguardando'
        ORDER BY id ASC
        LIMIT 1
    """).fetchone()

    if not cliente:
        flash("Não há clientes aguardando.", "erro")
        conn.close()
        return redirect(url_for("index"))

    conn.execute("""
        UPDATE clientes
        SET status = 'em atendimento',
            iniciado_em = ?
        WHERE id = ?
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        cliente["id"]
    ))

    conn.commit()
    conn.close()

    flash(
        f"Senha {cliente['senha']} - {cliente['nome']} foi chamada.",
        "sucesso"
    )

    return redirect(url_for("index"))


@app.route("/status/<int:id>", methods=["POST"])
def alterar_status(id):
    novo_status = request.form.get("status")

    status_permitidos = [
        "aguardando",
        "em atendimento",
        "concluído"
    ]

    if novo_status not in status_permitidos:
        flash("Status inválido.", "erro")
        return redirect(url_for("index"))

    conn = conectar_banco()

    if novo_status == "em atendimento":
        iniciado_em = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("""
            UPDATE clientes
            SET status = ?,
                iniciado_em = ?
            WHERE id = ?
        """, (
            novo_status,
            iniciado_em,
            id
        ))

    elif novo_status == "concluído":
        concluido_em = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("""
            UPDATE clientes
            SET status = ?,
                concluido_em = ?
            WHERE id = ?
        """, (
            novo_status,
            concluido_em,
            id
        ))

    else:
        conn.execute("""
            UPDATE clientes
            SET status = ?
            WHERE id = ?
        """, (
            novo_status,
            id
        ))

    conn.commit()
    conn.close()

    flash("Status atualizado com sucesso.", "sucesso")

    return redirect(url_for("index"))


@app.route("/cancelar/<int:id>", methods=["POST"])
def cancelar(id):
    conn = conectar_banco()

    conn.execute("""
        UPDATE clientes
        SET status = 'cancelado'
        WHERE id = ?
    """, (id,))

    conn.commit()
    conn.close()

    flash("Atendimento cancelado.", "sucesso")

    return redirect(url_for("index"))


if __name__ == "__main__":
    criar_banco()

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )
