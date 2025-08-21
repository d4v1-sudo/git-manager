import os
import subprocess
import sys
import json
import shutil
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

current_repo = None
repos_folder = os.path.join(os.getcwd(), "repos")
config_file = os.path.join(repos_folder, ".gitmanager_config.json")

# Configurações
config = {
    "github_token": None,
    "default_branch": "main",
    "auto_fetch": True,
    "editor": "nano"
}

def load_config():
    """Carrega configurações do arquivo JSON"""
    global config
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                saved_config = json.load(f)
                config.update(saved_config)
                # Garante que user.name e user.email estejam no config
                if 'user.name' not in config:
                    config['user.name'] = None
                if 'user.email' not in config:
                    config['user.email'] = None
        except Exception as e:
            print(f"Erro ao carregar configurações: {e}")

def save_config():
    """Salva configurações no arquivo JSON"""
    if not os.path.exists(repos_folder):
        os.makedirs(repos_folder)
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Erro ao salvar configurações: {e}")

def set_git_identity(repo_specific=False):
    """Configura user.name e user.email no Git (global ou repositório atual)"""
    if not config.get('user.name') or not config.get('user.email'):
        print("⚠️ Identidade Git não configurada (user.name ou user.email faltando).")
        return False
    
    scope = ["--local"] if repo_specific and current_repo else ["--global"]
    try:
        run_git(["config"] + scope + ["user.name", config['user.name']], show_output=False)
        run_git(["config"] + scope + ["user.email", config['user.email']], show_output=False)
        print(f"✅ Identidade Git configurada {'localmente' if repo_specific else 'globalmente'}: {config['user.name']} <{config['user.email']}>")
        return True
    except Exception as e:
        print(f"❌ Erro ao configurar identidade Git: {e}")
        return False

def set_github_token(token, name=None, email=None):
    """Configura token do GitHub e identidade do usuário"""
    config["github_token"] = token
    if name:
        config["user.name"] = name
    if email:
        config["user.email"] = email
    
    save_config()
    
    # Configura identidade Git globalmente se name e email foram fornecidos
    if name and email:
        set_git_identity(repo_specific=False)
    
    print("✅ Token GitHub configurado com sucesso!")
    if name and email:
        print(f"✅ Identidade Git configurada: {name} <{email}>")

def auto_login():
    """Automatiza o login com token do GitHub e configura identidade"""
    # Tenta obter o token de uma variável de ambiente
    token = os.getenv("GITHUB_TOKEN")
    
    if not token:
        # Se não houver variável de ambiente, solicita o token
        token = input("🔑 Digite seu token do GitHub (ou pressione Enter para pular): ").strip()
        if not token:
            print("⚠️ Nenhum token fornecido. Algumas operações podem falhar.")
            return
    
    # Solicita nome e e-mail se não estiverem configurados
    name = config.get("user.name")
    email = config.get("user.email")
    
    if not name:
        name = input("👤 Digite seu nome para commits Git: ").strip()
    if not email:
        email = input("📧 Digite seu e-mail para commits Git: ").strip()
    
    # Configura token e identidade
    set_github_token(token, name, email)

def quick_commit(message):
    """Faz commit rápido de todas as mudanças"""
    print("📝 Adicionando arquivos...")
    if not run_git(["add", "."]):
        return
    
    # Garante que a identidade esteja configurada antes do commit
    if not config.get('user.name') or not config.get('user.email'):
        print("⚠️ Identidade Git não configurada. Configurando agora...")
        name = input("👤 Digite seu nome para commits Git: ").strip()
        email = input("📧 Digite seu e-mail para commits Git: ").strip()
        if name and email:
            config["user.name"] = name
            config["user.email"] = email
            save_config()
        else:
            print("❌ Nome e e-mail são obrigatórios para fazer commits.")
            return
    
    # Sempre configura a identidade no repositório atual antes do commit
    if not set_git_identity(repo_specific=True):
        return
    
    # Verifica e configura rastreamento para a branch atual
    result = run_git(["branch", "--show-current"], show_output=False, return_output=True)
    if result:
        current_branch = result.stdout.strip()
        branch_result = run_git(["branch", "-vv"], show_output=False, return_output=True)
        if branch_result and f"[origin/{current_branch}]" not in branch_result.stdout:
            print(f"⚠️ Branch '{current_branch}' não está rastreando uma branch remota. Configurando...")
            run_git(["branch", "--set-upstream-to", f"origin/{current_branch}", current_branch])
    
    print("💾 Fazendo commit...")
    if run_git(["commit", "-m", message]):
        print(f"✅ Commit '{message}' realizado!")
    else:
        print("❌ Falha no commit. Verifique se há mudanças para commitar.")

def run_git(args, show_output=True, return_output=False):
    """Executa comandos git no repositório atual"""
    if current_repo is None:
        print("❌ Nenhum repositório selecionado. Use 'cd <repo>' ou 'clone <url>'")
        return None
    
    try:
        result = subprocess.run(
            ["git"] + args, 
            cwd=current_repo, 
            text=True, 
            capture_output=True,
            timeout=30
        )
        
        if return_output:
            return result
        
        if show_output:
            if result.stdout:
                print(result.stdout.strip())
            if result.stderr:  # Sempre exibe stderr se houver conteúdo
                print(f"⚠️ {result.stderr.strip()}")
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("⏱️ Comando git expirou (timeout 30s)")
        return False
    except Exception as e:
        print(f"❌ Erro ao executar git: {e}")
        return False

def list_projects():
    """Lista arquivos do repositório atual ou todos os projetos git clonados"""
    if current_repo:
        print(f"📁 Arquivos no repositório atual ({os.path.basename(current_repo)}):")
        print("-" * 80)
        try:
            # Lista arquivos no diretório do repositório atual, excluindo .git
            for item in os.listdir(current_repo):
                if item != ".git":
                    path = os.path.join(current_repo, item)
                    item_type = "📁" if os.path.isdir(path) else "📄"
                    print(f"{item_type} {item}")
        except Exception as e:
            print(f"❌ Erro ao listar arquivos: {e}")
        return

    # Caso nenhum repositório esteja selecionado, lista projetos
    if not os.path.exists(repos_folder):
        print("📂 Nenhuma pasta de repositórios encontrada.")
        return
    
    projects = []
    for d in os.listdir(repos_folder):
        path = os.path.join(repos_folder, d)
        if os.path.isdir(path) and os.path.isdir(os.path.join(path, ".git")):
            try:
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=path,
                    text=True,
                    capture_output=True
                )
                remote_url = result.stdout.strip() if result.returncode == 0 else "sem remote"
                
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=path,
                    text=True,
                    capture_output=True
                )
                current_branch = result.stdout.strip() if result.returncode == 0 else "unknown"
                
                projects.append({
                    'name': d,
                    'path': path,
                    'remote': remote_url,
                    'branch': current_branch,
                    'current': path == current_repo
                })
            except:
                projects.append({
                    'name': d,
                    'path': path,
                    'remote': "erro ao ler",
                    'branch': "erro ao ler",
                    'current': path == current_repo
                })
    
    if not projects:
        print("📂 Nenhum repositório encontrado.")
        return
    
    print(f"📋 Repositórios encontrados ({len(projects)}):")
    print("-" * 80)
    for proj in projects:
        marker = "👉" if proj['current'] else "  "
        print(f"{marker} {proj['name']:<20} | {proj['branch']:<15} | {proj['remote']}")

def debug_git_config():
    """Debug das configurações do Git"""
    if current_repo:
        print("🔍 Debug Git Config:")
        print(f"Config token: {config.get('github_token', 'None')[:20]}..." if config.get('github_token') else "None")
        
        result = run_git(["remote", "get-url", "origin"], show_output=False, return_output=True)
        if result:
            print(f"Remote URL: {result.stdout.strip()}")
        
        result = run_git(["config", "--list"], show_output=False, return_output=True)
        if result:
            lines = result.stdout.split('\\n')
            for line in lines:
                if 'credential' in line or 'github' in line:
                    print(f"Git config: {line}")

def change_project(name):
    """Muda para um projeto específico"""
    global current_repo
    
    if name == "..":
        current_repo = None
        print("Saindo do projeto atual.")
        return
    
    path = os.path.join(repos_folder, name)
    if os.path.isdir(path) and os.path.isdir(os.path.join(path, ".git")):
        current_repo = path
        print(f"📁 Projeto '{name}' selecionado.")
        
        # Configura credenciais do Git
        configure_git_credentials()
        
        # Auto-fetch se habilitado
        if config.get("auto_fetch", True):
            print("🔄 Atualizando informações do remoto...")
            run_git(["fetch"], show_output=False)
        
        # Mostra status rápido
        quick_status()
    else:
        print(f"❌ Projeto '{name}' não encontrado. Use 'list' para ver projetos disponíveis.")

def clone_project(url, folder_name=None):
    """Clona um repositório do GitHub"""
    try:
        # Extrai nome da pasta se não fornecido
        if not folder_name:
            if url.endswith('.git'):
                folder_name = os.path.basename(url)[:-4]
            else:
                folder_name = os.path.basename(url)
        
        target_path = os.path.join(repos_folder, folder_name)
        
        # Verifica se já existe
        if os.path.exists(target_path):
            print(f"❌ Pasta '{folder_name}' já existe!")
            return
        
        # Prepara URL com token se necessário
        clone_url = url
        if config.get("github_token") and url.startswith("https://github.com/"):
            parts = url.split("https://github.com/")
            clone_url = f"https://{config['github_token']}@github.com/{parts[1]}"
        
        print(f"📥 Clonando {url}...")
        result = subprocess.run(
            ["git", "clone", clone_url, folder_name],
            cwd=repos_folder,
            text=True,
            capture_output=True
        )
        
        if result.returncode == 0:
            print(f"✅ Clone concluído! Pasta: {folder_name}")
            # Auto-seleciona o projeto clonado
            change_project(folder_name)
        else:
            print(f"❌ Erro ao clonar: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Erro ao clonar: {e}")

def quick_status():
    """Mostra status resumido do repositório"""
    if current_repo is None:
        return
    
    # Branch atual
    result = run_git(["branch", "--show-current"], show_output=False, return_output=True)
    if result:
        branch = result.stdout.strip()
        print(f"🌿 Branch: {branch}")
    
    # Status das mudanças
    result = run_git(["status", "--porcelain"], show_output=False, return_output=True)
    if result:
        changes = result.stdout.strip().split('\n') if result.stdout.strip() else []
        if changes and changes[0]:
            print(f"📝 {len(changes)} arquivo(s) modificado(s)")
        else:
            print("✨ Diretório limpo")
    
    # Commits ahead/behind
    result = run_git(["status", "-uno"], show_output=False, return_output=True)
    if result and result.stdout:
        lines = result.stdout.split('\n')
        for line in lines:
            if 'ahead' in line or 'behind' in line:
                print(f"🔄 {line.strip()}")
                break

def status_changes():
    """Mostra status detalhado das mudanças"""
    print("📊 Status do repositório:")
    print("-" * 50)
    run_git(["status"])

def show_branches():
    """Mostra todas as branches"""
    print("🌿 Branches:")
    print("-" * 30)
    run_git(["branch", "-a"])

def switch_branch(branch_name, create=False):
    """Troca ou cria uma branch"""
    if create:
        if run_git(["checkout", "-b", branch_name]):
            print(f"✅ Branch '{branch_name}' criada e selecionada!")
    else:
        if run_git(["checkout", branch_name]):
            print(f"✅ Mudou para branch '{branch_name}'!")

def show_log(lines=10):
    """Mostra histórico de commits"""
    print(f"📜 Últimos {lines} commits:")
    print("-" * 60)
    run_git(["log", f"-{lines}", "--oneline", "--graph", "--decorate"])

def quick_push(branch=None):
    """Faz push rápido"""
    if current_repo is None:
        print("❌ Nenhum repositório selecionado.")
        return
    
    # Obtém a branch atual se nenhuma for especificada
    if branch is None:
        result = run_git(["branch", "--show-current"], show_output=False, return_output=True)
        if not result or not result.stdout.strip():
            print("❌ Não foi possível determinar a branch atual.")
            return
        branch = result.stdout.strip()
    
    # Verifica se há commits para enviar
    result = run_git(["log", "--oneline", f"origin/{branch}..{branch}"], show_output=False, return_output=True)
    if not result or not result.stdout.strip():
        print(f"ℹ️ Nenhum commit novo para enviar em '{branch}'.")
        return
    
    # Verifica rastreamento
    result = run_git(["branch", "-vv"], show_output=False, return_output=True)
    if result and f"[origin/{branch}]" not in result.stdout:
        print(f"⚠️ Branch '{branch}' não está rastreando uma branch remota. Configurando...")
        run_git(["branch", "--set-upstream-to", f"origin/{branch}", branch])
    
    print(f"🚀 Fazendo push para '{branch}'...")
    result = run_git(["push", "origin", branch], show_output=True, return_output=True)
    if result and result.returncode == 0:
        print("✅ Push concluído!")
        if result.stdout:
            print(f"Saída: {result.stdout.strip()}")
        if result.stderr:
            print(f"Aviso: {result.stderr.strip()}")
    else:
        print("❌ Falha no push. Verifique conexão, permissões ou regras de proteção.")
        if result and result.stderr:
            print(f"Erro: {result.stderr.strip()}")

def quick_pull(branch=None):
    """Faz pull rápido"""
    if branch is None:
        branch = config.get("default_branch", "main")
    
    print(f"📥 Fazendo pull de '{branch}'...")
    if run_git(["pull", "origin", branch]):
        print("✅ Pull concluído!")
    else:
        print("❌ Falha no pull. Verifique conflitos.")

def check_remote_diff():
    """Verifica diferenças com o repositório remoto"""
    if current_repo is None:
        print("❌ Nenhum projeto selecionado.")
        return
    
    print("🔄 Atualizando informações do remoto...")
    run_git(["fetch"])
    
    print("\n📊 Status comparado ao remoto:")
    result = subprocess.run(["git", "status", "-uno"], cwd=current_repo, text=True, capture_output=True)
    print(result.stdout)

def analyze_changes():
    """Analisa mudanças e sugere mensagens de commit"""
    if current_repo is None:
        print("❌ Nenhum repositório selecionado.")
        return None
    
    # Pega arquivos modificados
    result = run_git(["status", "--porcelain"], show_output=False, return_output=True)
    if not result or not result.stdout.strip():
        print("✨ Nenhuma mudança detectada!")
        return None
    
    changes = result.stdout.strip().split('\n')
    
    # Categoriza mudanças
    added_files = []
    modified_files = []
    deleted_files = []
    renamed_files = []
    
    for line in changes:
        status = line[:2]
        filename = line[3:]
        
        if 'A' in status:
            added_files.append(filename)
        elif 'M' in status:
            modified_files.append(filename)
        elif 'D' in status:
            deleted_files.append(filename)
        elif 'R' in status:
            renamed_files.append(filename)
    
    return {
        'added': added_files,
        'modified': modified_files,
        'deleted': deleted_files,
        'renamed': renamed_files,
        'total': len(changes)
    }

def get_file_extension_stats(files):
    """Analisa extensões dos arquivos para determinar tipo de mudança"""
    extensions = defaultdict(int)
    categories = defaultdict(list)
    
    for file in files:
        ext = Path(file).suffix.lower()
        extensions[ext] += 1
        
        # Categoriza por tipo
        if ext in ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs']:
            categories['code'].append(file)
        elif ext in ['.css', '.scss', '.less', '.html', '.vue', '.jsx', '.tsx']:
            categories['frontend'].append(file)
        elif ext in ['.md', '.txt', '.rst']:
            categories['docs'].append(file)
        elif ext in ['.json', '.yaml', '.yml', '.xml', '.toml']:
            categories['config'].append(file)
        elif ext in ['.sql']:
            categories['database'].append(file)
        elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg']:
            categories['images'].append(file)
        else:
            categories['other'].append(file)
    
    return extensions, categories

def analyze_diff_content():
    """Analisa o conteúdo das mudanças para sugestões mais inteligentes"""
    if current_repo is None:
        return {}
    
    # Pega diff das mudanças
    result = run_git(["diff", "--cached"], show_output=False, return_output=True)
    if not result:
        # Se não há nada no stage, pega diff de tudo
        result = run_git(["diff"], show_output=False, return_output=True)
    
    if not result or not result.stdout:
        return {}
    
    diff_content = result.stdout
    
    # Analisa padrões no diff
    patterns = {
        'bug_fixes': [
            r'\bfix\b', r'\bbug\b', r'\berror\b', r'\bissue\b',
            r'\.catch\(', r'try\s*{', r'except:', r'throw\s+new',
            r'console\.error', r'logger\.error'
        ],
        'features': [
            r'\badd\b', r'\bnew\b', r'\bimplement\b', r'\bcreate\b',
            r'function\s+\w+', r'def\s+\w+', r'class\s+\w+',
            r'export\s+', r'import\s+'
        ],
        'refactoring': [
            r'\brefactor\b', r'\bclean\b', r'\boptimize\b',
            r'rename', r'move', r'extract'
        ],
        'tests': [
            r'\btest\b', r'\bspec\b', r'describe\(', r'it\(',
            r'assert', r'expect\(', r'@test'
        ],
        'docs': [
            r'README', r'\.md', r'documentation', r'comment',
            r'#\s', r'\/\*\*', r'"""'
        ],
        'style': [
            r'format', r'indent', r'whitespace', r'style',
            r'\.css', r'\.scss', r'color:', r'font-'
        ]
    }
    
    detected_patterns = {}
    for category, pattern_list in patterns.items():
        count = 0
        for pattern in pattern_list:
            matches = re.findall(pattern, diff_content, re.IGNORECASE)
            count += len(matches)
        if count > 0:
            detected_patterns[category] = count
    
    return detected_patterns

def generate_commit_suggestions(changes_info):
    """Gera sugestões de mensagem de commit baseadas nas mudanças"""
    if not changes_info:
        return []
    
    suggestions = []
    
    # Analisa extensões e categorias
    all_files = (changes_info['added'] + changes_info['modified'] + 
                changes_info['deleted'] + changes_info['renamed'])
    
    extensions, categories = get_file_extension_stats(all_files)
    patterns = analyze_diff_content()
    
    # Sugestões baseadas em padrões de diff
    if 'bug_fixes' in patterns and patterns['bug_fixes'] > 2:
        suggestions.append("🐛 Fix: Corrige bugs encontrados")
        suggestions.append("🔧 Bugfix: Resolve problemas identificados")
    
    if 'features' in patterns and patterns['features'] > 3:
        suggestions.append("✨ Feat: Adiciona nova funcionalidade")
        suggestions.append("🚀 Feature: Implementa nova feature")
    
    if 'refactoring' in patterns and patterns['refactoring'] > 1:
        suggestions.append("♻️ Refactor: Reestrutura código")
        suggestions.append("🔨 Refactor: Melhora estrutura do código")
    
    if 'tests' in patterns and patterns['tests'] > 2:
        suggestions.append("✅ Test: Adiciona/atualiza testes")
        suggestions.append("🧪 Tests: Melhora cobertura de testes")
    
    if 'docs' in patterns and patterns['docs'] > 1:
        suggestions.append("📝 Docs: Atualiza documentação")
        suggestions.append("📚 Documentation: Melhora docs do projeto")
    
    if 'style' in patterns and patterns['style'] > 2:
        suggestions.append("💄 Style: Ajustes de formatação e estilo")
        suggestions.append("🎨 UI: Melhorias visuais")
    
    # Sugestões baseadas em tipos de arquivos
    if len(categories['config']) > 0:
        suggestions.append("⚙️ Config: Atualiza configurações")
    
    if len(categories['database']) > 0:
        suggestions.append("🗃️ Database: Atualiza esquemas/queries")
    
    if len(categories['frontend']) >= len(categories['code']) and categories['frontend']:
        suggestions.append("💻 UI: Atualiza interface do usuário")
        suggestions.append("🌐 Frontend: Melhorias no frontend")
    
    # Sugestões baseadas em operações
    if len(changes_info['added']) > len(changes_info['modified']) + len(changes_info['deleted']):
        suggestions.append(f"➕ Add: Adiciona {len(changes_info['added'])} novos arquivos")
    
    if len(changes_info['deleted']) > 0:
        suggestions.append(f"🗑️ Remove: Remove {len(changes_info['deleted'])} arquivos")
    
    if len(changes_info['renamed']) > 0:
        suggestions.append(f"🚚 Rename: Reorganiza {len(changes_info['renamed'])} arquivos")
    
    # Sugestões genéricas baseadas na quantidade
    total = changes_info['total']
    if total == 1:
        filename = all_files[0] if all_files else "arquivo"
        suggestions.append(f"📝 Update: Atualiza {Path(filename).name}")
    elif total <= 3:
        suggestions.append(f"🔄 Update: Pequenas atualizações ({total} arquivos)")
    else:
        suggestions.append(f"🚀 Major: Grandes mudanças ({total} arquivos)")
    
    # Remove duplicatas mantendo ordem
    seen = set()
    unique_suggestions = []
    for suggestion in suggestions:
        if suggestion not in seen:
            seen.add(suggestion)
            unique_suggestions.append(suggestion)
    
    return unique_suggestions[:8]  # Limita a 8 sugestões

def smart_status():
    """Status inteligente com análise de mudanças e sugestões"""
    print("🔍 Analisando mudanças...")
    print("-" * 50)
    
    changes_info = analyze_changes()
    if not changes_info:
        return
    
    # Mostra resumo das mudanças
    print(f"📊 Resumo das mudanças:")
    if changes_info['added']:
        print(f"  ➕ {len(changes_info['added'])} arquivo(s) adicionado(s)")
    if changes_info['modified']:
        print(f"  📝 {len(changes_info['modified'])} arquivo(s) modificado(s)")
    if changes_info['deleted']:
        print(f"  🗑️ {len(changes_info['deleted'])} arquivo(s) removido(s)")
    if changes_info['renamed']:
        print(f"  🚚 {len(changes_info['renamed'])} arquivo(s) renomeado(s)")
    
    # Mostra detalhes dos arquivos
    print(f"\n📁 Arquivos afetados:")
    all_files = (changes_info['added'] + changes_info['modified'] + 
                changes_info['deleted'] + changes_info['renamed'])
    
    extensions, categories = get_file_extension_stats(all_files)
    
    for category, files in categories.items():
        if files:
            icon = {
                'code': '💻', 'frontend': '🌐', 'docs': '📚',
                'config': '⚙️', 'database': '🗃️', 'images': '🖼️', 'other': '📄'
            }.get(category, '📄')
            print(f"  {icon} {category.title()}: {', '.join(files[:3])}" + 
                  (f" (+{len(files)-3} mais)" if len(files) > 3 else ""))
    
    # Gera e mostra sugestões
    suggestions = generate_commit_suggestions(changes_info)
    
    if suggestions:
        print(f"\n💡 Sugestões de commit:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {i}. {suggestion}")
        
        print(f"\n🎯 Comandos sugeridos:")
        print(f"  smart-commit [número]  - Usa sugestão por número")
        print(f"  smart-commit          - Usa primeira sugestão")
        print(f"  commit \"sua mensagem\" - Commit personalizado")
        
        return suggestions
    
    return []

def smart_commit(suggestion_number=None, custom_message=None):
    """Faz commit inteligente baseado em análise ou sugestão"""
    if custom_message:
        quick_commit(custom_message)
        return
    
    changes_info = analyze_changes()
    if not changes_info:
        print("❌ Nenhuma mudança para commit!")
        return
    
    suggestions = generate_commit_suggestions(changes_info)
    
    if not suggestions:
        print("❌ Não foi possível gerar sugestões. Use commit manual.")
        return
    
    # Determina qual sugestão usar
    if suggestion_number is not None:
        try:
            index = int(suggestion_number) - 1
            if 0 <= index < len(suggestions):
                selected_message = suggestions[index]
            else:
                print(f"❌ Número inválido. Use 1-{len(suggestions)}")
                return
        except ValueError:
            print("❌ Número inválido!")
            return
    else:
        # Usa a primeira sugestão (mais relevante)
        selected_message = suggestions[0]
    
    # Remove emoji e prefixo para mensagem limpa
    clean_message = selected_message
    
    print(f"🤖 Commit sugerido: {clean_message}")
    confirm = input("Confirma este commit? (s/N): ").lower()
    
    if confirm in ['s', 'sim', 'yes', 'y']:
        quick_commit(clean_message)
    else:
        print("❌ Commit cancelado.")

def auto_stage_and_suggest():
    """Automaticamente adiciona arquivos ao stage e sugere commit"""
    if current_repo is None:
        print("❌ Nenhum repositório selecionado.")
        return
    
    # Verifica se há mudanças
    result = run_git(["status", "--porcelain"], show_output=False, return_output=True)
    if not result or not result.stdout.strip():
        print("✨ Nenhuma mudança detectada!")
        return
    
    # Adiciona arquivos automaticamente (exceto alguns padrões)
    print("📝 Adicionando arquivos modificados...")
    
    # Lista arquivos para adicionar (filtra alguns padrões)
    changes = result.stdout.strip().split('\n')
    files_to_add = []
    
    for line in changes:
        filename = line[3:]
        # Ignora arquivos temporários e sensíveis
        if not any(pattern in filename.lower() for pattern in 
                  ['.log', '.tmp', 'node_modules/', '.env', '__pycache__/', '.pyc']):
            files_to_add.append(filename)
    
    if files_to_add:
        # Adiciona arquivo por arquivo para melhor controle
        for file in files_to_add:
            run_git(["add", file], show_output=False)
        
        print(f"✅ {len(files_to_add)} arquivo(s) adicionado(s) ao stage")
        
        # Mostra sugestões
        suggestions = smart_status()
        
        if suggestions:
            print(f"\n⚡ Quer fazer commit agora?")
            choice = input("Digite o número da sugestão ou 'n' para cancelar: ").strip()
            
            if choice.lower() not in ['n', 'no', 'não']:
                try:
                    if choice.isdigit():
                        smart_commit(choice)
                    else:
                        smart_commit(1)  # Usa primeira sugestão
                except:
                    print("❌ Opção inválida. Use 'smart-status' para ver sugestões novamente.")
    else:
        print("⚠️ Nenhum arquivo adequado para adicionar encontrado.")

def workflow_suggestions():
    """Sugere próximos passos no workflow baseado no estado atual"""
    if current_repo is None:
        print("❌ Nenhum repositório selecionado.")
        return
    
    print("🔮 Análise do workflow atual:")
    print("-" * 40)
    
    # Verifica status
    unstaged = run_git(["diff", "--name-only"], show_output=False, return_output=True)
    staged = run_git(["diff", "--cached", "--name-only"], show_output=False, return_output=True)
    untracked = run_git(["ls-files", "--others", "--exclude-standard"], show_output=False, return_output=True)
    
    # Verifica commits não enviados
    result = run_git(["log", "--oneline", "@{u}..HEAD"], show_output=False, return_output=True)
    unpushed_commits = len(result.stdout.strip().split('\n')) if result and result.stdout.strip() else 0
    
    # Verifica branch atual
    branch_result = run_git(["branch", "--show-current"], show_output=False, return_output=True)
    current_branch = branch_result.stdout.strip() if branch_result else "unknown"
    
    suggestions = []
    
    if untracked and untracked.stdout.strip():
        untracked_files = untracked.stdout.strip().split('\n')
        suggestions.append(f"📁 {len(untracked_files)} arquivo(s) não rastreado(s) - considere 'auto-stage'")
    
    if unstaged and unstaged.stdout.strip():
        unstaged_files = unstaged.stdout.strip().split('\n')
        suggestions.append(f"📝 {len(unstaged_files)} arquivo(s) modificado(s) - use 'smart-status' ou 'auto-stage'")
    
    if staged and staged.stdout.strip():
        staged_files = staged.stdout.strip().split('\n')
        suggestions.append(f"✅ {len(staged_files)} arquivo(s) preparado(s) - pronto para 'smart-commit'")
    
    if unpushed_commits > 0:
        suggestions.append(f"🚀 {unpushed_commits} commit(s) não enviado(s) - considere 'push'")
    
    if current_branch != config.get("default_branch", "main"):
        suggestions.append(f"🌿 Você está na branch '{current_branch}' - merge/push quando pronto")
    
    # Verifica se pode fazer pull
    run_git(["fetch"], show_output=False)
    result = run_git(["log", "--oneline", "HEAD..@{u}"], show_output=False, return_output=True)
    unpulled_commits = len(result.stdout.strip().split('\n')) if result and result.stdout.strip() else 0
    
    if unpulled_commits > 0:
        suggestions.append(f"📥 {unpulled_commits} commit(s) disponível(is) no remoto - considere 'pull'")
    
    if not suggestions:
        suggestions.append("✨ Tudo limpo! Pronto para trabalhar.")
    
    print("💡 Sugestões de próximos passos:")
    for i, suggestion in enumerate(suggestions, 1):
        print(f"  {i}. {suggestion}")
    
    # Sugestões de comandos
    print(f"\n🛠️ Comandos úteis:")
    print(f"  auto-stage    - Adiciona arquivos e sugere commit")
    print(f"  smart-status  - Análise detalhada com sugestões")
    print(f"  workflow      - Esta análise")
    print(f"  quick-sync    - Pull + Push rápido")

def show_config():
    """Mostra configurações atuais"""
    print("⚙️  Configurações atuais:")
    print("-" * 30)
    for key, value in config.items():
        if key == "github_token" and value:
            print(f"{key}: {'*' * 10}")  # Mascarar token
        else:
            print(f"{key}: {value}")

def set_config(key, value):
    """Define uma configuração"""
    if key in config:
        if key in ["auto_fetch"]:
            config[key] = value.lower() in ['true', '1', 'yes', 'sim']
        else:
            config[key] = value
        save_config()
        print(f"✅ {key} = {config[key]}")
    else:
        print(f"❌ Configuração '{key}' não existe. Use 'config' para ver opções disponíveis.")

def show_help(cmd=None):
    """Exibe ajuda detalhada dos comandos"""
    help_text = {
        "help": {
            "desc": "Exibe esta ajuda",
            "usage": "help [comando]",
            "examples": ["help", "help clone", "help commit"]
        },
        "exit": {
            "desc": "Sai do programa",
            "usage": "exit",
            "examples": ["exit"]
        },
        "list": {
            "desc": "Lista todos os repositórios clonados com informações detalhadas",
            "usage": "list",
            "examples": ["list"]
        },
        "cd": {
            "desc": "Seleciona um repositório para trabalhar",
            "usage": "cd <nome-do-repo> | cd ..",
            "examples": ["cd meu-projeto", "cd .."]
        },
        "clone": {
            "desc": "Clona um repositório do GitHub (público ou privado com token)",
            "usage": "clone <url> [nome-pasta]",
            "examples": ["clone https://github.com/user/repo.git", "clone https://github.com/user/repo.git minha-pasta"]
        },
        "status": {
            "desc": "Mostra status detalhado do repositório atual",
            "usage": "status",
            "examples": ["status"]
        },
        "branch": {
            "desc": "Lista todas as branches ou cria/muda para uma branch. -c para criar uma nova",
            "usage": "branch [nome] [-c]",
            "examples": ["branch", "branch feature/nova", "branch feature/nova -c"]
        },
        "log": {
            "desc": "Mostra histórico de commits",
            "usage": "log [quantidade]",
            "examples": ["log", "log 20"]
        },
        "commit": {
            "desc": "Adiciona todos os arquivos e faz commit com mensagem",
            "usage": "commit <mensagem>",
            "examples": ["commit \"Adiciona nova funcionalidade\"", "commit \"Fix: corrige bug na validação\""]
        },
        "add": {
            "desc": "Adiciona arquivo(s) ao stage ou copia arquivo de outra branch",
            "usage": "add <arquivo> | add <branch> -- <arquivo>",
            "examples": ["add arquivo.txt", "add main -- logo.svg", "add feature/nova -- config.json"]
        },
        "merge": {
            "desc": "Faz merge de outra branch na branch atual",
            "usage": "merge <branch>",
            "examples": ["merge develop", "merge feature/nova"]
        },
        "push": {
            "desc": "Envia commits para o repositório remoto",
            "usage": "push [branch]",
            "examples": ["push", "push develop", "push feature/nova"]
        },
        "pull": {
            "desc": "Baixa e mescla mudanças do repositório remoto",
            "usage": "pull [branch]",
            "examples": ["pull", "pull main"]
        },
        "diff": {
            "desc": "Mostra diferenças entre local e remoto",
            "usage": "diff",
            "examples": ["diff"]
        },
        "delete": {
            "desc": "Remove um repositório local completamente",
            "usage": "delete <nome-repo>",
            "examples": ["delete projeto-antigo"]
        },
        "login": {
            "desc": "Configura token do GitHub para repositórios privados",
            "usage": "login <token>",
            "examples": ["login ghp_xxxxxxxxxxxxxxxxxxxx"]
        },
        "config": {
            "desc": "Mostra ou define configurações do sistema",
            "usage": "config [chave] [valor]",
            "examples": ["config", "config default_branch develop", "config auto_fetch false"]
        },
        "smart-status": {
            "desc": "Status inteligente com análise de mudanças e sugestões de commit",
            "usage": "smart-status",
            "examples": ["smart-status"]
        },
        "smart-commit": {
            "desc": "Commit inteligente baseado em análise das mudanças",
            "usage": "smart-commit [número] | smart-commit \"mensagem\"",
            "examples": ["smart-commit", "smart-commit 2", "smart-commit \"Fix: corrige bug crítico\""]
        },
        "auto-stage": {
            "desc": "Adiciona arquivos automaticamente e sugere commits",
            "usage": "auto-stage",
            "examples": ["auto-stage"]
        },
        "workflow": {
            "desc": "Analisa estado atual e sugere próximos passos",
            "usage": "workflow",
            "examples": ["workflow"]
        },
        "quick-sync": {
            "desc": "Sincronização rápida (pull + push se necessário)",
            "usage": "quick-sync",
            "examples": ["quick-sync"]
        },
    }
    
    if cmd and cmd in help_text:
        info = help_text[cmd]
        print(f"\n📖 Comando: {cmd}")
        print(f"Descrição: {info['desc']}")
        print(f"Uso: {info['usage']}")
        if info.get('examples'):
            print("Exemplos:")
            for ex in info['examples']:
                print(f"  {ex}")
    elif cmd:
        print(f"❌ Comando '{cmd}' não encontrado.")
        print("Use 'help' para ver todos os comandos disponíveis.")
    else:
        print("🎯 Git Manager - Comandos Disponíveis:")
        print("=" * 50)
        
        categories = {
            "📁 Gerenciamento de Projetos": ["list", "cd", "clone", "delete", "merge"],
            "📝 Controle de Versão": ["status", "add", "branch", "log", "commit", "push", "pull", "diff"],
            "🤖 IA e Automação": ["smart-status", "smart-commit", "auto-stage", "workflow", "quick-sync"],
            "⚙️  Configuração": ["login", "config"],
            "❓ Ajuda": ["help", "exit"]
        }
        
        for category, commands in categories.items():
            print(f"\n{category}:")
            for cmd_name in commands:
                if cmd_name in help_text:
                    print(f"  {cmd_name:<12} - {help_text[cmd_name]['desc']}")
        
        print(f"\n💡 Use 'help <comando>' para ajuda detalhada.")

def clear():
    """Limpa o terminal e mostra o prompt atual"""
    try:
        # Executa o comando 'clear' apropriado para o sistema operacional
        os.system('cls' if os.name == 'nt' else 'clear')
        # Mostra o prompt atual
        prompt = f"📁 {os.path.basename(current_repo)}" if current_repo else "git-manager"
        # print(f"{prompt}> ", end="")
    except Exception as e:
        print(f"❌ Erro ao limpar terminal: {e}")

def delete_project(name):
    """Remove um repositório local completamente"""
    path = os.path.join(repos_folder, name)
    global current_repo
    
    if not os.path.exists(path):
        print(f"❌ Projeto '{name}' não encontrado.")
        return
    
    if not os.path.isdir(os.path.join(path, ".git")):
        print(f"❌ '{name}' não é um repositório git válido.")
        return
    
    confirm = input(f"⚠️ Tem certeza que deseja excluir '{name}' permanentemente? (s/N): ").lower()
    if confirm in ['s', 'sim', 'yes', 'y']:
        try:
            shutil.rmtree(path)
            print(f"🗑️ Projeto '{name}' excluído com sucesso!")
            
            # Se o projeto excluído era o atual, limpa a seleção
            if current_repo == path:
                current_repo = None
                print("Saindo do projeto atual.")
        except Exception as e:
            print(f"❌ Erro ao excluir projeto: {e}")
    else:
        print("❌ Exclusão cancelada.")

def quick_sync():
    """Realiza sincronização rápida (pull + push se necessário)"""
    if current_repo is None:
        print("❌ Nenhum repositório selecionado.")
        return
    
    # Pega branch atual
    result = run_git(["branch", "--show-current"], show_output=False, return_output=True)
    if not result:
        print("❌ Não foi possível determinar a branch atual.")
        return
    branch = result.stdout.strip()
    
    print(f"🔄 Sincronizando branch '{branch}'...")
    
    # Faz pull
    if run_git(["pull", "origin", branch]):
        print("✅ Pull concluído!")
    else:
        print("⚠️ Pull falhou. Verifique conflitos.")
        return
    
    # Verifica se há commits locais não enviados
    result = run_git(["log", "--oneline", "@{u}..HEAD"], show_output=False, return_output=True)
    has_unpushed = bool(result and result.stdout.strip())
    
    if has_unpushed:
        # Faz push se houver commits locais
        if run_git(["push", "origin", branch]):
            print("✅ Push concluído!")
        else:
            print("❌ Push falhou. Verifique conexão e permissões.")
    else:
        print("✨ Tudo sincronizado! Nenhum push necessário.")

def configure_git_credentials():
    """Configura credenciais do Git para usar o token automaticamente"""
    if not config.get("github_token") or not current_repo:
        return
        
    try:
        # Remove configurações antigas de credential
        run_git(["config", "--unset", "credential.helper"], show_output=False)
        run_git(["config", "--unset", "credential.https://github.com.username"], show_output=False)
        
        # Pega URL atual do remote
        result = run_git(["remote", "get-url", "origin"], show_output=False, return_output=True)
        if result and result.stdout.strip():
            current_url = result.stdout.strip()
            
            # Remove token antigo se existir
            if "@github.com" in current_url:
                clean_url = "https://github.com/" + current_url.split("@github.com/")[1]
            else:
                clean_url = current_url
            
            # Adiciona novo token
            if clean_url.startswith("https://github.com/"):
                new_url = clean_url.replace("https://github.com/", f"https://{config['github_token']}@github.com/")
                run_git(["remote", "set-url", "origin", new_url], show_output=False)
                print(f"🔧 Token configurado no remote")
    except Exception as e:
        print(f"⚠️ Erro ao configurar credenciais: {e}")

def merge_branch(source_branch, target_branch=None):
    """Faz merge de uma branch em outra após verificar mudanças pendentes"""
    if current_repo is None:
        print("❌ Nenhum repositório selecionado.")
        return
    
    # Obtém a branch atual se target_branch não for especificada
    if target_branch is None:
        result = run_git(["branch", "--show-current"], show_output=False, return_output=True)
        if not result or not result.stdout.strip():
            print("❌ Não foi possível determinar a branch atual.")
            return
        target_branch = result.stdout.strip()
    
    # Verifica se há mudanças pendentes
    result = run_git(["status", "--porcelain"], show_output=False, return_output=True)
    if result and result.stdout.strip():
        print("⚠️ Existem mudanças pendentes. Faça commit ou stash antes do merge.")
        return
    
    # Garante que estamos na branch alvo
    if run_git(["branch", "--show-current"], show_output=False, return_output=True).stdout.strip() != target_branch:
        if not run_git(["checkout", target_branch]):
            print(f"❌ Falha ao mudar para a branch '{target_branch}'.")
            return
    
    # Faz o merge
    print(f"🔄 Fazendo merge da branch '{source_branch}' em '{target_branch}'...")
    result = run_git(["merge", source_branch], show_output=True, return_output=True)
    if result and result.returncode == 0:
        print(f"✅ Merge concluído! Branch '{source_branch}' mesclada em '{target_branch}'.")
    else:
        print("❌ Falha no merge. Verifique conflitos ou se a branch existe.")
        if result and result.stderr:
            print(f"Erro: {result.stderr.strip()}")

def add_file_from_branch(branch_name, file_path):
    """Adiciona um arquivo específico de outra branch ao stage atual"""
    if current_repo is None:
        print("❌ Nenhum repositório selecionado.")
        return
    
    print(f"📝 Adicionando '{file_path}' da branch '{branch_name}'...")
    
    # Verifica se a branch existe
    result = run_git(["branch", "-a"], show_output=False, return_output=True)
    if result and branch_name not in result.stdout:
        print(f"❌ Branch '{branch_name}' não encontrada.")
        return
    
    # Usa git checkout para copiar o arquivo da branch
    if run_git(["checkout", branch_name, "--", file_path]):
        # Adiciona o arquivo ao stage
        if run_git(["add", file_path]):
            print(f"✅ Arquivo '{file_path}' adicionado da branch '{branch_name}' ao stage!")
        else:
            print(f"❌ Erro ao adicionar '{file_path}' ao stage.")
    else:
        print(f"❌ Erro ao copiar arquivo da branch '{branch_name}'.")

def main():
    """Função principal do programa"""
    global current_repo
    
    # Carrega configurações
    load_config()
    debug_git_config()
    
    # Cria pasta de repositórios se não existir
    if not os.path.exists(repos_folder):
        os.makedirs(repos_folder)
    
    print("🚀 Git Manager Iniciado!")
    print("Digite 'help' para ver comandos disponíveis.\n")
    
    while True:
        # Mostra prompt com projeto atual
        prompt = f"📁 {os.path.basename(current_repo)}" if current_repo else "git-manager"
        
        try:
            cmd_input = input(f"{prompt}> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Saindo... Até logo!")
            break
        
        if not cmd_input:
            continue

        parts = cmd_input.split()
        cmd = parts[0].lower()
        args = parts[1:]

        # Processamento de comandos
        if cmd == "exit" or cmd == "quit":
            print("👋 Até logo!")
            break
        elif cmd == "help" or cmd == "?":
            show_help(args[0] if args else None)
        elif cmd == "list" or cmd == "ls":
            list_projects()
        elif cmd == "cd":
            if args:
                change_project(args[0])
            else:
                print("❌ Uso: cd <projeto>")
        elif cmd == "clone":
            if args:
                folder_name = args[1] if len(args) > 1 else None
                clone_project(args[0], folder_name)
            else:
                print("❌ Uso: clone <url> [nome-pasta]")
        elif cmd == "status":
            status_changes()
        elif cmd == "smart-status" or cmd == "ss":
            smart_status()
        elif cmd == "smart-commit" or cmd == "sc":
            if args and not args[0].isdigit():
                # É uma mensagem personalizada
                smart_commit(custom_message=" ".join(args))
            elif args:
                # É um número de sugestão
                smart_commit(args[0])
            else:
                # Usa primeira sugestão
                smart_commit()
        elif cmd == "auto-stage" or cmd == "as":
            auto_stage_and_suggest()
        elif cmd == "workflow" or cmd == "wf":
            workflow_suggestions()
        elif cmd == "quick-sync" or cmd == "sync":
            quick_sync()
        elif cmd == "branch":
            if len(args) == 0:
                show_branches()
            elif len(args) >= 1:
                create_flag = "-c" in args
                branch_name = args[0]
                switch_branch(branch_name, create_flag)
        elif cmd == "log":
            lines = int(args[0]) if args and args[0].isdigit() else 10
            show_log(lines)
        elif cmd == "commit":
            if args:
                quick_commit(" ".join(args))
            else:
                print("❌ Uso: commit <mensagem>")
        elif cmd == "push":
            branch = args[0] if args else None
            quick_push(branch)
        elif cmd == "pull":
            branch = args[0] if args else None
            quick_pull(branch)
        elif cmd == "diff":
            check_remote_diff()
        elif cmd == "delete" or cmd == "rm":
            if args:
                delete_project(args[0])
            else:
                print("❌ Uso: delete <nome-repo>")
        elif cmd == "login":
            if args:
                set_github_token(args[0])
            else:
                print("❌ Uso: login <token>")
        elif cmd == "config":
            if len(args) == 0:
                show_config()
            elif len(args) == 2:
                set_config(args[0], args[1])
            else:
                print("❌ Uso: config [chave] [valor]")
        elif cmd == "clear" or cmd == "cls":
            clear()
        elif cmd == "debug":
            debug_git_config()
        elif cmd == "mkdir":
            if args:
                base_path = current_repo if current_repo else os.getcwd()
                new_folder = os.path.join(base_path, args[0])
                if not os.path.exists(new_folder):
                    os.makedirs(new_folder)
                    print(f"📂 Pasta '{args[0]}' criada com sucesso!")
                else:
                    print(f"⚠️ Pasta '{args[0]}' já existe.")
            else:
                print("❌ Uso: mkdir <nome-pasta>")
        elif cmd == "merge":
            if len(args) >= 1:
                source_branch = args[0]
                target_branch = args[1] if len(args) > 1 else None
                merge_branch(source_branch, target_branch)
            else:
                print("❌ Uso: merge <source-branch> [target-branch]")
        elif cmd == "add":
            if len(args) >= 3 and args[1] == "--":
                # Formato: add <branch> -- <arquivo>
                branch_name = args[0]
                file_path = args[2]
                add_file_from_branch(branch_name, file_path)
            elif args:
                # Formato tradicional: add <arquivo>
                for file_path in args:
                    if run_git(["add", file_path]):
                        print(f"✅ '{file_path}' adicionado ao stage!")
                    else:
                        print(f"❌ Erro ao adicionar '{file_path}'.")
            else:
                print("❌ Uso: add <arquivo> | add <branch> -- <arquivo>")
        else:
            print(f"❌ Comando '{cmd}' não reconhecido.")
            print("💡 Use 'help' para ver comandos disponíveis.")

if __name__ == "__main__":
    main()
