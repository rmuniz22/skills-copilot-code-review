# API de Atividades da Mergington High School

Uma aplicação FastAPI super simples que permite aos alunos visualizar e se inscrever em atividades extracurriculares.

## Funcionalidades

- Visualizar todas as atividades extracurriculares disponíveis
- Inscrever e remover estudantes de atividades (somente usuários autenticados)
- Exibir anúncios ativos no topo da página
- Gerenciar anúncios com criação, edição e exclusão (somente usuários autenticados)

## Como começar

1. Instale as dependências:

   ```
   pip install fastapi uvicorn
   ```

2. Execute a aplicação:

   ```
   python app.py
   ```

3. Abra seu navegador e acesse:
   - Documentação da API: http://localhost:8000/docs
   - Documentação alternativa: http://localhost:8000/redoc

## Endpoints da API

| Método | Endpoint | Descrição |
| ------ | -------- | --------- |
| GET | `/activities` | Obtém todas as atividades com detalhes e número atual de participantes |
| POST | `/activities/{activity_name}/signup?email=student@mergington.edu&teacher_username={username}` | Inscreve estudante na atividade (autenticação obrigatória) |
| POST | `/activities/{activity_name}/unregister?email=student@mergington.edu&teacher_username={username}` | Remove estudante da atividade (autenticação obrigatória) |
| POST | `/auth/login?username={username}&password={password}` | Realiza login de professor/direção |
| GET | `/auth/check-session?username={username}` | Valida sessão salva no cliente |
| GET | `/announcements` | Lista anúncios ativos (considera início opcional e expiração obrigatória) |
| GET | `/announcements/manage?teacher_username={username}` | Lista todos os anúncios para gerenciamento (autenticação obrigatória) |
| POST | `/announcements?teacher_username={username}` | Cria anúncio (expiração obrigatória, início opcional) |
| PUT | `/announcements/{announcement_id}?teacher_username={username}` | Atualiza anúncio existente |
| DELETE | `/announcements/{announcement_id}?teacher_username={username}` | Exclui anúncio |

## Modelo de Dados

A aplicação usa MongoDB com identificadores significativos:

1. **Atividades** - Usa o nome da atividade como identificador:
   - Descrição
   - Horário
   - Número máximo de participantes permitidos
   - Lista de e-mails dos alunos inscritos

2. **Professores** - Usa o username como identificador:
   - Nome de exibição
   - Senha com hash Argon2
   - Papel (teacher/admin)

3. **Anúncios** - Usa slug do título como identificador:
   - Título
   - Mensagem
   - Data de início (opcional)
   - Data de expiração (obrigatória)
   - Usuário criador

Dados iniciais de atividades, professores e um anúncio de exemplo são inseridos automaticamente quando as coleções estão vazias.
