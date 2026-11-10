# Escala Certa

Planejador de escalas para restaurantes de São Paulo. Abra **Montar minha escala** para cadastrar unidade, equipe e demanda. O exemplo do Bistrô Alameda fica separado.

[Abrir o Escala Certa online](https://murilomarchesan-png.github.io/escala-certa/). O cálculo e o rascunho ficam no navegador.

## Rodar

Requer Python 3.11 ou mais recente, sem instalação de bibliotecas. No Windows, abra **Abrir Escala Certa.cmd** pelo Explorador de Arquivos ou rode:

```powershell
cd C:/Users/muril/Downloads/EscalaCerta
python apps/api/server.py
```

Abra [http://127.0.0.1:8765](http://127.0.0.1:8765). Se preferir contêiner e tiver Docker instalado, execute `docker compose up --build`.

1. Carregue o restaurante fictício e confira o período, as pessoas e os turnos.
2. Ajuste as quantidades mínimas e desejadas. Selecione 44h, 42h ou 40h como hipótese.
3. Gere a escala. Alterne entre as opções e confira a cobertura e os conflitos. Remova ou adicione uma alocação para recalcular.
4. Baixe o Excel completo. Para PDF, selecione semana e equipe, clique em **Imprimir / Salvar PDF** e escolha **Salvar como PDF** no navegador.

O rascunho e a escala editada ficam neste navegador. Exporte antes de limpar seus dados locais. Use identificadores internos e revise a escala antes de aplicá-la.

## Testes

```powershell
python -m unittest discover -s tests -v
node --check apps/web/app.js
```

## Escopo e evolução

O simulador oferece uma unidade, demanda configurável por dia da semana e turnos com uma função por alocação. A busca tem 18 tentativas, semente 141, e ordena os resultados por cobertura mínima e desejada. Preferência de folga e distribuição de domingos influenciam a busca. O limite móvel de dias é conservador e usa dias civis com trabalho. Ele não equivale à apuração de repousos remunerados.

O lançamento do PRD ainda depende de CP-SAT, cobertura distinta por data, persistência das versões, fronteiras entre ciclos, autenticação e publicação, isolamento de unidades, links individuais, financeiro e matriz jurídica revisada. A licença de distribuição permanece em decisão. [Arquitetura e riscos](docs/architecture/DECISOES.md) · [Revisão jurídica pendente](docs/legal/LEGAL_REVIEW_REQUIRED.md)
