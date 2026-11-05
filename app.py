from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
import os
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2 import IntegrityError

app = Flask(__name__)
app.secret_key = 'troque-esta-chave-antes-de-publicar'
def ligar_banco():
    """Conecta ao banco PostgreSQL criado pelo pgAdmin."""
    banco = psycopg2.connect(
        host="localhost",
        database="bibliotec",
        user="postgres",
        password="senai",
        port=5432
    )
    return ConexaoBanco(banco)


def conectar():
    return ligar_banco()


class ConexaoBanco:
    """Pequeno adaptador para manter o estilo simples db.execute(...) usado no app."""
    def __init__(self, conexao):
        self.conexao = conexao

    def execute(self, sql, parametros=None):
        cursor = self.conexao.cursor(cursor_factory=DictCursor)
        cursor.execute(sql, parametros or ())
        return cursor

    def executemany(self, sql, parametros):
        cursor = self.conexao.cursor(cursor_factory=DictCursor)
        cursor.executemany(sql, parametros)
        return cursor

    def executescript(self, sql):
        cursor = self.conexao.cursor()
        for comando in sql.split(';'):
            if comando.strip():
                cursor.execute(comando)
        cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, tipo_erro, erro, rastreamento):
        try:
            if tipo_erro is None:
                self.conexao.commit()
            else:
                self.conexao.rollback()
        finally:
            self.conexao.close()


def iniciar_banco():
    with conectar() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS livros (
            id SERIAL PRIMARY KEY,
            titulo TEXT NOT NULL,
            autor TEXT NOT NULL,
            genero TEXT NOT NULL,
            ano INTEGER,
            descricao TEXT NOT NULL,
            capa TEXT,
            paginas INTEGER DEFAULT 1,
            publico_domaino INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS capitulos (
            id SERIAL PRIMARY KEY,
            livro_id INTEGER NOT NULL,
            numero INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            FOREIGN KEY (livro_id) REFERENCES livros(id) ON DELETE CASCADE,
            UNIQUE(livro_id, numero)
        );
        CREATE TABLE IF NOT EXISTS favoritos (
            usuario_id INTEGER NOT NULL,
            livro_id INTEGER NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(usuario_id, livro_id),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY(livro_id) REFERENCES livros(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS progresso_leitura (
            usuario_id INTEGER NOT NULL,
            livro_id INTEGER NOT NULL,
            capitulo_numero INTEGER DEFAULT 1,
            pagina INTEGER DEFAULT 1,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(usuario_id, livro_id),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY(livro_id) REFERENCES livros(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS comentarios (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            livro_id INTEGER NOT NULL,
            texto TEXT NOT NULL,
            nota INTEGER DEFAULT 5 CHECK(nota BETWEEN 1 AND 5),
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY(livro_id) REFERENCES livros(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS mensagens_contato (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        quantidade = db.execute('SELECT COUNT(*) FROM livros').fetchone()[0]
        if quantidade == 0:
            livros = [
                ('Dom Casmurro', 'Machado de Assis', 'Romance', 1899, 'As memórias de Bentinho revisitam sua juventude, sua relação com Capitu e as dúvidas que marcaram sua vida.', '/static/img/Dom Casmurro.jpg', 250),
                ('O Alienista', 'Machado de Assis', 'Conto', 1882, 'Uma narrativa satírica sobre ciência, poder e os limites entre razão e loucura.', '/static/img/O Alienista.jpg', 96),
                ('A Escrava Isaura', 'Bernardo Guimarães', 'Romance', 1875, 'Romance abolicionista que acompanha a trajetória de Isaura em busca de liberdade.', '/static/img/A Escrava Isaura.jpg', 220),
                ('Memórias Póstumas de Brás Cubas', 'Machado de Assis', 'Clássico', 1881, 'Narrado por um defunto autor, o livro apresenta uma reflexão irônica sobre a sociedade.', '/static/img/Memórias Póstumas de Brás Cubas.jpg', 300),
                ('A Moreninha', 'Joaquim Manuel de Macedo', 'Romance', 1844, 'Um romance brasileiro sobre promessas, encontros e amores da juventude.', '/static/img/a_moreninha.jpg', 180),
                ('Poemas Escolhidos', 'Diversos autores', 'Poesia', 1900, 'Uma pequena seleção de poemas e textos de domínio público para descobrir novos estilos.', '', 60),
            ]
            db.executemany('INSERT INTO livros (titulo,autor,genero,ano,descricao,capa,paginas) VALUES (%s,%s,%s,%s,%s,%s,%s)', livros)
            textos = {
                'Dom Casmurro': [
                    ('Do título', 'Uma noite destas, vindo da cidade para o Engenho Novo, encontrei no trem da Central um rapaz aqui do bairro, que eu conheço de vista e de chapéu.\n\nCumprimentou-me, sentou-se ao pé de mim, falou da lua e dos ministros, e acabou recitando-me versos. A viagem era curta, e os versos podem ser longos.\n\nA conversa daquela noite deu origem a lembranças que o narrador tenta organizar em páginas.'),
                    ('Do livro', 'O narrador explica por que decidiu reunir suas memórias. Ao revisitar o passado, percebe que reconstruir uma história também significa escolher o que contar e como contar.'),
                    ('A denúncia', 'As recordações seguem para a juventude de Bentinho e para as relações familiares que influenciaram seus caminhos. Este capítulo de demonstração contém um resumo, não a reprodução integral da obra.')],
                'O Alienista': [('A chegada de Simão Bacamarte', 'Simão Bacamarte retorna à cidade de Itaguaí e decide dedicar-se ao estudo da mente humana. Sua iniciativa logo provoca curiosidade e desconfiança entre os moradores.'), ('A Casa Verde', 'O médico funda uma instituição para estudar os comportamentos que considera fora da razão. A população começa a questionar os critérios usados para definir a loucura.'), ('A revolta', 'As decisões de Bacamarte afetam a vida da cidade e geram conflitos. A narrativa usa humor e ironia para questionar autoridade e certezas científicas.')],
                'A Escrava Isaura': [('A fazenda', 'Isaura é apresentada como uma jovem escravizada que recebeu educação e vive sob a opressão de uma sociedade injusta. Sua história coloca em evidência a violência da escravidão.'), ('A decisão', 'Diante das ameaças e das limitações impostas, Isaura busca uma saída para conquistar a própria liberdade.'), ('Em busca de liberdade', 'A trajetória da personagem acompanha os riscos, as escolhas e as pessoas que cruzam seu caminho.')]
            }
            for titulo, capitulos in textos.items():
                livro_id = db.execute('SELECT id FROM livros WHERE titulo=%s', (titulo,)).fetchone()['id']
                for numero, (nome, conteudo) in enumerate(capitulos, start=1):
                    db.execute('INSERT INTO capitulos (livro_id,numero,titulo,conteudo) VALUES (%s,%s,%s,%s)', (livro_id, numero, nome, conteudo))
            # Demais títulos recebem capítulos demonstrativos simples.
            for livro in db.execute('SELECT id,titulo FROM livros WHERE id NOT IN (SELECT DISTINCT livro_id FROM capitulos)').fetchall():
                for numero, nome in enumerate(['Apresentação', 'Primeiras páginas', 'Continuação'], start=1):
                    db.execute('INSERT INTO capitulos (livro_id,numero,titulo,conteudo) VALUES (%s,%s,%s,%s)', (livro['id'], numero, nome, f'Este é um trecho demonstrativo de {livro["titulo"]}. O conteúdo completo pode ser cadastrado no banco de dados pela equipe do projeto.'))

        # Atualiza as capas também para quem já possui os livros cadastrados.
        capas = {
            'Dom Casmurro': '/static/img/Dom Casmurro.jpg',
            'O Alienista': '/static/img/O Alienista.jpg',
            'A Escrava Isaura': '/static/img/A Escrava Isaura.jpg',
            'Memórias Póstumas de Brás Cubas': '/static/img/Memórias Póstumas de Brás Cubas.jpg',
            'A Moreninha': '/static/img/a_moreninha.jpg',
        }
        for titulo, capa in capas.items():
            db.execute('UPDATE livros SET capa=%s WHERE titulo=%s', (capa, titulo))

    # Os capítulos reais são importados pelo arquivo importar_capitulos.py.
    # Não sobrescreva o conteúdo do leitor com resumos ao iniciar o servidor.


def usuario_atual():
    if 'usuario_id' not in session:
        return None
    with conectar() as db:
        return db.execute('SELECT id,nome,email FROM usuarios WHERE id=%s', (session['usuario_id'],)).fetchone()


def livro_por_id(db, livro_id):
    livro = db.execute('SELECT * FROM livros WHERE id=%s', (livro_id,)).fetchone()
    if livro is None:
        abort(404)
    return livro


@app.context_processor
def contexto_global():
    return {'usuario': usuario_atual()}


@app.route('/')
def inicio():
    with conectar() as db:
        livros = db.execute('SELECT * FROM livros ORDER BY id DESC LIMIT 4').fetchall()
    return render_template('index.html', livros=livros)


@app.route('/catalogo')
def catalogo():
    busca = request.args.get('busca', '').strip()
    genero = request.args.get('genero', '').strip()
    ordem = request.args.get('ordem', 'titulo')
    ordenacoes = {'titulo': 'titulo', 'recentes': 'ano DESC', 'autor': 'autor'}
    sql = 'SELECT * FROM livros WHERE (titulo ILIKE %s OR autor ILIKE %s OR descricao ILIKE %s)'
    parametros = [f'%{busca}%', f'%{busca}%', f'%{busca}%']
    if genero and genero != 'Todos':
        sql += ' AND genero=%s'
        parametros.append(genero)
    sql += ' ORDER BY ' + ordenacoes.get(ordem, 'titulo')
    with conectar() as db:
        livros = db.execute(sql, parametros).fetchall()
        generos = db.execute('SELECT DISTINCT genero FROM livros ORDER BY genero').fetchall()
    return render_template('catalogo.html', livros=livros, generos=generos, busca=busca, genero=genero, ordem=ordem)


@app.route('/livro/<int:livro_id>')
def detalhe_livro(livro_id):
    with conectar() as db:
        livro = livro_por_id(db, livro_id)
        capitulos = db.execute('SELECT * FROM capitulos WHERE livro_id=%s ORDER BY numero', (livro_id,)).fetchall()
        comentarios = db.execute('SELECT comentarios.*, usuarios.nome FROM comentarios JOIN usuarios ON usuarios.id=comentarios.usuario_id WHERE livro_id=%s ORDER BY comentarios.id DESC', (livro_id,)).fetchall()
        favorito = False
        if session.get('usuario_id'):
            favorito = db.execute('SELECT 1 FROM favoritos WHERE usuario_id=%s AND livro_id=%s', (session['usuario_id'], livro_id)).fetchone() is not None
    return render_template('livro.html', livro=livro, capitulos=capitulos, comentarios=comentarios, favorito=favorito)


@app.route('/ler/<int:livro_id>')
def leitura(livro_id):
    numero = request.args.get('capitulo', 1, type=int)
    with conectar() as db:
        livro = livro_por_id(db, livro_id)
        capitulos = db.execute('SELECT * FROM capitulos WHERE livro_id=%s ORDER BY numero', (livro_id,)).fetchall()
        if not capitulos:
            abort(404)
        capitulo = db.execute('SELECT * FROM capitulos WHERE livro_id=%s AND numero=%s', (livro_id, numero)).fetchone()
        if capitulo is None:
            capitulo = capitulos[0]
            numero = capitulo['numero']
        if session.get('usuario_id'):
            db.execute('INSERT INTO progresso_leitura(usuario_id,livro_id,capitulo_numero,pagina) VALUES (%s,%s,%s,1) ON CONFLICT(usuario_id,livro_id) DO UPDATE SET capitulo_numero=excluded.capitulo_numero, atualizado_em=CURRENT_TIMESTAMP', (session['usuario_id'], livro_id, numero))
    return render_template('leitura.html', livro=livro, capitulos=capitulos, capitulo=capitulo)


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        if not nome or not email or len(senha) < 6:
            flash('Preencha todos os campos. A senha precisa ter pelo menos 6 caracteres.', 'erro')
        else:
            try:
                with conectar() as db:
                    db.execute('INSERT INTO usuarios(nome,email,senha) VALUES (%s,%s,%s)', (nome, email, generate_password_hash(senha)))
                flash('Conta criada! Agora você pode entrar.', 'sucesso')
                return redirect(url_for('login'))
            except IntegrityError:
                flash('Este e-mail já está cadastrado.', 'erro')
    return render_template('cadastro.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        with conectar() as db:
            conta = db.execute('SELECT * FROM usuarios WHERE email=%s', (email,)).fetchone()
        if conta and check_password_hash(conta['senha'], senha):
            session['usuario_id'] = conta['id']
            flash('Login realizado com sucesso.', 'sucesso')
            return redirect(url_for('biblioteca'))
        flash('E-mail ou senha incorretos.', 'erro')
    return render_template('login.html')


@app.route('/sair')
def sair():
    session.clear()
    flash('Você saiu da sua conta.', 'sucesso')
    return redirect(url_for('inicio'))


def exigir_login():
    if not session.get('usuario_id'):
        flash('Entre na sua conta para usar esse recurso.', 'erro')
        return False
    return True


@app.route('/favoritar/<int:livro_id>', methods=['POST'])
def favoritar(livro_id):
    if not exigir_login():
        return redirect(url_for('login'))
    with conectar() as db:
        livro_por_id(db, livro_id)
        existe = db.execute('SELECT 1 FROM favoritos WHERE usuario_id=%s AND livro_id=%s', (session['usuario_id'], livro_id)).fetchone()
        if existe:
            db.execute('DELETE FROM favoritos WHERE usuario_id=%s AND livro_id=%s', (session['usuario_id'], livro_id))
            flash('Livro removido dos favoritos.', 'sucesso')
        else:
            db.execute('INSERT INTO favoritos(usuario_id,livro_id) VALUES (%s,%s)', (session['usuario_id'], livro_id))
            flash('Livro adicionado aos favoritos.', 'sucesso')
    return redirect(request.referrer or url_for('catalogo'))


@app.route('/biblioteca')
def biblioteca():
    if not exigir_login():
        return redirect(url_for('login'))
    with conectar() as db:
        livros = db.execute('SELECT livros.*, progresso_leitura.capitulo_numero FROM progresso_leitura JOIN livros ON livros.id=progresso_leitura.livro_id WHERE progresso_leitura.usuario_id=%s ORDER BY atualizado_em DESC', (session['usuario_id'],)).fetchall()
    return render_template('biblioteca.html', livros=livros)


@app.route('/favoritos')
def favoritos():
    if not exigir_login():
        return redirect(url_for('login'))
    with conectar() as db:
        livros = db.execute('SELECT livros.* FROM favoritos JOIN livros ON livros.id=favoritos.livro_id WHERE favoritos.usuario_id=%s ORDER BY favoritos.criado_em DESC', (session['usuario_id'],)).fetchall()
    return render_template('favoritos.html', livros=livros)


@app.route('/comunidade', methods=['GET', 'POST'])
def comunidade():
    if request.method == 'POST':
        if not exigir_login():
            return redirect(url_for('login'))
        texto = request.form.get('texto', '').strip()
        livro_id = request.form.get('livro_id', type=int)
        nota = request.form.get('nota', 5, type=int)
        if texto and livro_id:
            with conectar() as db:
                livro_por_id(db, livro_id)
                db.execute('INSERT INTO comentarios(usuario_id,livro_id,texto,nota) VALUES (%s,%s,%s,%s)', (session['usuario_id'], livro_id, texto, max(1, min(5, nota))))
            flash('Comentário publicado.', 'sucesso')
            return redirect(url_for('comunidade'))
        flash('Escolha um livro e escreva um comentário.', 'erro')
    with conectar() as db:
        comentarios = db.execute('SELECT comentarios.*, usuarios.nome, livros.titulo FROM comentarios JOIN usuarios ON usuarios.id=comentarios.usuario_id JOIN livros ON livros.id=comentarios.livro_id ORDER BY comentarios.id DESC').fetchall()
        livros = db.execute('SELECT id,titulo FROM livros ORDER BY titulo').fetchall()
    return render_template('comunidade.html', comentarios=comentarios, livros=livros)


@app.route('/contato', methods=['GET', 'POST'])
def contato():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip()
        mensagem = request.form.get('mensagem', '').strip()
        if nome and email and mensagem:
            with conectar() as db:
                db.execute('INSERT INTO mensagens_contato(nome,email,mensagem) VALUES (%s,%s,%s)', (nome, email, mensagem))
            flash('Mensagem enviada! Obrigado pelo contato.', 'sucesso')
            return redirect(url_for('contato'))
        flash('Preencha todos os campos.', 'erro')
    return render_template('contato.html')


@app.route('/admin')
def admin():
    with conectar() as db:
        totais = {
            'usuarios': db.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0],
            'livros': db.execute('SELECT COUNT(*) FROM livros').fetchone()[0],
            'comentarios': db.execute('SELECT COUNT(*) FROM comentarios').fetchone()[0],
            'mensagens': db.execute('SELECT COUNT(*) FROM mensagens_contato').fetchone()[0],
        }
        livros = db.execute('SELECT * FROM livros ORDER BY id DESC').fetchall()
    return render_template('admin.html', totais=totais, livros=livros)


@app.route('/api/livros')
def api_livros():
    busca = request.args.get('busca', '').strip()
    with conectar() as db:
        livros = db.execute('SELECT id,titulo,autor,genero,ano,descricao,capa,paginas FROM livros WHERE titulo ILIKE %s OR autor ILIKE %s ORDER BY titulo', (f'%{busca}%', f'%{busca}%')).fetchall()
    return [dict(livro) for livro in livros]


@app.errorhandler(404)
def pagina_nao_encontrada(_erro):
    return render_template('404.html'), 404


iniciar_banco()

if __name__ == '__main__':
    app.run(debug=True)
