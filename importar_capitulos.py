"""Importa capítulos integrais de domínio público do Wikisource para o Bibliotec.
Execute depois de criar o banco e iniciar o projeto ao menos uma vez:
    python importar_capitulos.py
É necessária conexão com a internet na primeira importação.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
import psycopg2

API = 'https://pt.wikisource.org/w/api.php'

class TextoHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.partes=[]; self.ignorar=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','sup'): self.ignorar += 1
        if tag in ('p','br','div','h1','h2','h3','li'): self.partes.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style','sup') and self.ignorar: self.ignorar -= 1
        if tag in ('p','div','h1','h2','h3','li'): self.partes.append('\n')
    def handle_data(self, data):
        if not self.ignorar: self.partes.append(data)
    def texto(self):
        texto=''.join(self.partes)
        texto=re.sub(r'[ \t]+',' ',texto)
        texto=re.sub(r'\n\s*\n+', '\n\n', texto)
        return texto.strip()

def api(params):
    url=API+'?'+urllib.parse.urlencode({'format':'json','formatversion':2,**params})
    req=urllib.request.Request(url,headers={'User-Agent':'BibliotecEscolar/1.0 (importacao de obras em dominio publico)'})
    with urllib.request.urlopen(req,timeout=40) as r: return json.loads(r.read().decode('utf-8'))

def html_text(html):
    parser=TextoHTML(); parser.feed(html); return parser.texto()

def secoes_da_pagina(pagina):
    dados=api({'action':'parse','page':pagina,'prop':'sections'})['parse']['sections']
    saida=[]
    for sec in dados:
        nivel=int(sec.get('level','0'))
        if nivel < 2: continue
        indice=sec['index']
        conteudo=api({'action':'parse','page':pagina,'section':indice,'prop':'text'})['parse']['text']
        texto=html_text(conteudo)
        if len(texto)>80:
            titulo=re.sub(r'\s+',' ',sec.get('line','')).strip()
            saida.append((titulo or f'Seção {len(saida)+1}',texto))
        time.sleep(.08)
    return saida

def alienista():
    romanos=['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII']
    saida=[]
    for i,r in enumerate(romanos,1):
        pagina=f'O Alienista/{r}'
        try:
            dados=api({'action':'parse','page':pagina,'prop':'text'})
            html=dados['parse']['text']; texto=html_text(html)
            # O título da página costuma vir no primeiro cabeçalho.
            parser=TextoHTML(); parser.feed(html)
            titulo=f'Capítulo {r}'
            for linha in parser.texto().splitlines():
                if 'Capítulo' in linha or 'capítulo' in linha:
                    titulo=linha.strip(); break
            if len(texto)>80: saida.append((titulo,texto))
        except Exception as e: print(f'Não foi possível obter {pagina}: {e}')
        time.sleep(.08)
    return saida

OBRAS={
 'Dom Casmurro':'Anexo:Imprimir/Dom Casmurro',
 'Memórias Póstumas de Brás Cubas':'Anexo:Imprimir/Memórias Póstumas de Brás Cubas',
 'A Moreninha':'Anexo:Imprimir/A Moreninha',
 'A Escrava Isaura':'Anexo:Imprimir/A escrava Isaura',
}

def main():
    capitulos={}
    for nome,pagina in OBRAS.items():
        print('Buscando',nome)
        capitulos[nome]=secoes_da_pagina(pagina)
        print(' ',len(capitulos[nome]),'capítulos/seções encontrados')
    capitulos['O Alienista']=alienista()
    if any(not v for v in capitulos.values()):
        raise SystemExit('A importação ficou incompleta. Verifique a conexão e tente novamente; o banco não foi alterado.')
    db=psycopg2.connect(host='localhost',database='bibliotec',user='postgres',password='senai',port=5432)
    try:
        cur=db.cursor()
        for nome,lista in capitulos.items():
            cur.execute('SELECT id FROM livros WHERE titulo=%s',(nome,)); row=cur.fetchone()
            if not row: print('Livro não encontrado:',nome); continue
            livro_id=row[0]
            cur.execute('DELETE FROM capitulos WHERE livro_id=%s',(livro_id,))
            for numero,(titulo,conteudo) in enumerate(lista,1):
                cur.execute('INSERT INTO capitulos (livro_id,numero,titulo,conteudo) VALUES (%s,%s,%s,%s)',(livro_id,numero,titulo,conteudo))
            print(f'{nome}: {len(lista)} capítulos importados.')
        db.commit()
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
    print('Importação concluída! Fonte: Wikisource (obras em domínio público).')

if __name__=='__main__': main()
