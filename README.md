# Prevision API: contas e histórico

Além dos endpoints existentes de previsão, a API oferece cadastro, login e histórico de relatórios demonstrativos. Esses relatórios não representam uma previsão real: a integração com a análise de imagens ainda será implementada.

## Configuração

1. Instale as dependências da API com `pip install -r requirements.txt` no mesmo ambiente Python.
2. Crie um banco MySQL dedicado `prevision_app` e um usuário com permissões para criar tabelas e ler, inserir, atualizar e excluir os dados desse banco.
3. Copie `.env.example` para `.env` e preencha as credenciais localmente. Não inclua esse arquivo no Git.
4. Execute `schema.sql` uma vez no banco dedicado usando o MySQL Workbench ou outro cliente. O script cria as tabelas `app_users`, `app_sessions` e `app_reports`.
5. Inicie a API com `python app.py`. Para configurar CORS, defina `CORS_ORIGINS` como uma lista de origens separadas por vírgula. Sem essa variável, permanecem as origens anteriores, incluindo `http://localhost:4200`.

Os endpoints `/auth/register`, `/auth/login`, `/auth/me`, `/auth/logout` e `/reports` estão documentados em `/docs`. Login retorna um token de sessão com validade de 12 horas; envie-o no cabeçalho `Authorization: Bearer <token>`. O histórico e as imagens são restritos ao usuário autenticado. Imagens JPEG, PNG ou WebP de até 5 MB são armazenadas no MySQL e excluídas com o relatório.

O cliente de demonstração guarda o token em `sessionStorage` na aba atual. Antes de disponibilizar publicamente, é necessário configurar HTTPS, backups, controle de tentativas de login e políticas de retenção e privacidade, além de revisar a segurança e dimensionar o armazenamento.

`GET /health/ready` verifica a conexão MySQL e o acesso às tabelas de contas e relatórios. Os testes de integração MySQL são executados quando `TEST_MYSQL=1`; use apenas um banco de teste dedicado, com `schema.sql` já aplicado.
