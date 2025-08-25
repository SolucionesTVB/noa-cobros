#!/bin/bash
set -euo pipefail

echo "🚀 Preparando deploy de Noa Cobros..."

# .gitignore básico
if [ ! -f .gitignore ]; then
  cat > .gitignore <<'GIT'
backend/.venv/
__pycache__/
*.pyc
noa_cobros.db
GIT
fi

# 1. Inicia repo si no existe
if [ ! -d ".git" ]; then
  git init
  echo "✔ Repo inicializado"
fi

# 2. Agrega y commitea
git add .
git commit -m "Deploy automático Noa Cobros" || echo "ℹ️ Nada nuevo para commitear"

# 3. Remote origin: usa GitHub CLI si está disponible; si no, pide URL
if ! git remote | grep -q origin; then
  if command -v gh >/dev/null 2>&1; then
    gh repo create noa-cobros --public --source . --remote origin --push
    echo "✔ Repo creado y subido con gh"
  else
    echo "👉 Pegá la URL de tu repo en GitHub (ej: https://github.com/TuUsuario/noa-cobros.git):"
    read REPO
    git remote add origin "$REPO"
    git branch -M main
    git push -u origin main
    echo "✔ Código empujado a $REPO"
  fi
else
  git branch -M main
  git push -u origin main
fi

echo
echo "✅ Código en GitHub."
echo
echo "👉 Render:"
echo "   - Entra a https://render.com > New > Blueprint"
echo "   - Seleccioná este repo. Usará render.yaml y levantará el backend con gunicorn."
echo
echo "👉 Netlify:"
echo "   - Entra a https://app.netlify.com > Add new site > Deploy manually"
echo "   - Arrastrá la carpeta /frontend. Te dará un link público (guárdalo en favoritos)."
echo
echo "📌 Una vez desplegado en Netlify, ése será tu link único para entrar siempre a Noa Cobros 🚀"
