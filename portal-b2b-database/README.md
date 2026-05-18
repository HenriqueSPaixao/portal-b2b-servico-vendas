# 🗄️ Portal B2B — Estrutura de Base de Dados (DDL)

Este repositório contém a documentação e os scripts oficiais de definição de dados (DDL) para o projeto **Portal B2B**. Como o ecossistema utiliza uma arquitetura de microsserviços com um banco de dados PostgreSQL compartilhado, este repositório serve como a **Single Source of Truth** para a estrutura do schema.

---

## 🏗️ Responsabilidades do DBA

- **Gestão de Schema:** Criação, alteração e manutenção de tabelas, índices e constraints.
- **Padronização:** Garantir que todos os serviços sigam os mesmos padrões de nomenclatura e tipos de dados.
- **Controle de Acessos:** Gestão das permissões para o usuário de manutenção (`db_portal_b2b`) e usuário de aplicação (`svc_portal_b2b`).
- **Integridade:** Validar se alterações propostas pelos times de microsserviços não geram redundância ou conflitos.

---

## 🔐 Dados de Conexão (Ambiente de Integração)

| Parâmetro | Valor |
|:---|:---|
| **Host** | `34.29.84.207` |
| **Porta** | `5432` |
| **Database** | `portal_b2b` |
| **Schema** | `portal_b2b` |
| **Usuário DBA** | `db_portal_b2b` |
| **Usuário App** | `svc_portal_b2b` |

> [!IMPORTANT]
> **REGRA INEGOCIÁVEL:** Os microsserviços **não possuem permissão** para criar ou alterar tabelas (DDL). O `auto-migrate` (ou equivalente) do seu ORM **deve estar desativado**. Qualquer alteração estrutural deve ser solicitada à equipe de BD.

---

## 📏 Padrões de Desenvolvimento

1. **Nomenclatura:** `snake_case` em tabelas e colunas.
2. **Identificadores:** `UUID` obrigatório, gerados via `gen_random_uuid()` (extensão `pgcrypto`).
3. **Timestamps:** Todas as tabelas devem conter `data_cadastro` e `ultima_alteracao` com `TIMESTAMPTZ`.
4. **Moeda/Quantidades:** `DECIMAL(18,4)`. **Nunca** usar `FLOAT`.
5. **Soft delete:** Campo `ativo BOOLEAN` nas entidades principais.
6. **Status:** Valores em `SCREAMING_SNAKE_CASE` (ex: `'ATIVO'`, `'PENDENTE'`).

> **Exceção:** O módulo de demanda utiliza `data_criacao` e `atualizado_em` por convenção da equipe responsável.

---

## 📂 Organização do Repositório

```text
.
├── doc/
│   └── doc_bd.md                           # Documentação completa do modelo ER
├── scripts/
│   ├── 01-initial.sql                      # Schema, roles, permissões e health_check
│   ├── 02-criacao_produtos.sql             # Módulo de produtos (tabelas, triggers, índices)
│   ├── 03-reorganizacao_permissoes.sql     # Ownership, grants e search_path
│   ├── 04-criacao_tabelas_principais.sql   # Tabelas principais do modelo
│   ├── 05-modulo_demanda.sql               # Módulo de demanda (novas tabelas + alterações)
│   └── 06-demanda_alinhamento.sql          # Ajustes finais de alinhamento com equipe de demanda
└── README.md
```

---

## ▶️ Ordem de Execução

Os scripts devem ser executados **em ordem** como usuário `db_portal_b2b`:

```bash
psql -h 34.29.84.207 -U db_portal_b2b -d portal_b2b -f scripts/01-initial.sql
psql -h 34.29.84.207 -U db_portal_b2b -d portal_b2b -f scripts/02-criacao_produtos.sql
psql -h 34.29.84.207 -U db_portal_b2b -d portal_b2b -f scripts/03-reorganizacao_permissoes.sql
psql -h 34.29.84.207 -U db_portal_b2b -d portal_b2b -f scripts/04-criacao_tabelas_principais.sql
psql -h 34.29.84.207 -U db_portal_b2b -d portal_b2b -f scripts/05-modulo_demanda.sql
psql -h 34.29.84.207 -U db_portal_b2b -d portal_b2b -f scripts/06-demanda_alinhamento.sql
```

---

## 📖 Documentação do Modelo

O detalhamento de todas as tabelas, colunas, constraints e relacionamentos está em [`doc/doc_bd.md`](doc/doc_bd.md).
