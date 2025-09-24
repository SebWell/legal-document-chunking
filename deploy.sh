#!/bin/bash
# Script de déploiement pour l'API de chunking sur VPS

set -e

echo "🚀 Déploiement de l'API Legal Chunking"

# Variables
APP_DIR="/opt/legal-chunking-api"
SERVICE_NAME="legal-chunking-api"
USER="www-data"

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Vérifier si on est root
if [ "$EUID" -ne 0 ]; then
    print_error "Ce script doit être exécuté en tant que root"
    exit 1
fi

# 1. Mise à jour du système
print_status "Mise à jour du système..."
apt update && apt upgrade -y

# 2. Installation de Python et pip si nécessaire
print_status "Installation de Python 3 et pip..."
apt install -y python3 python3-pip python3-venv

# 3. Création du répertoire de l'application
print_status "Création du répertoire de l'application..."
mkdir -p $APP_DIR
chown $USER:$USER $APP_DIR

# 4. Copie des fichiers
print_status "Copie des fichiers de l'application..."
cp main.py $APP_DIR/
cp requirements.txt $APP_DIR/
chown -R $USER:$USER $APP_DIR

# 5. Création de l'environnement virtuel
print_status "Création de l'environnement virtuel..."
cd $APP_DIR
sudo -u $USER python3 -m venv venv
sudo -u $USER ./venv/bin/pip install --upgrade pip
sudo -u $USER ./venv/bin/pip install -r requirements.txt

# 6. Test de l'installation
print_status "Test de l'installation..."
sudo -u $USER ./venv/bin/python -c "import fastapi, uvicorn; print('Dependencies OK')"

# 7. Création du service systemd
print_status "Création du service systemd..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=Legal Document Chunking API
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 8. Activation et démarrage du service
print_status "Activation du service..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# 9. Vérification du statut
sleep 3
if systemctl is-active --quiet $SERVICE_NAME; then
    print_status "✅ Service démarré avec succès"
    print_status "📍 API disponible sur : http://localhost:8000"
    print_status "📍 Documentation : http://localhost:8000/docs"
else
    print_error "❌ Échec du démarrage du service"
    print_error "Logs : journalctl -u $SERVICE_NAME -f"
    exit 1
fi

# 10. Configuration du firewall (optionnel)
print_warning "N'oubliez pas de configurer votre firewall si nécessaire :"
print_warning "ufw allow 8000"

# 11. Test de l'API
print_status "Test de l'API..."
sleep 2
if curl -s http://localhost:8000/health > /dev/null; then
    print_status "✅ API répond correctement"
else
    print_warning "⚠️  L'API ne répond pas encore, vérifiez les logs"
fi

print_status "🎉 Déploiement terminé !"
print_status ""
print_status "📋 Commandes utiles :"
print_status "  • Statut du service : systemctl status $SERVICE_NAME"
print_status "  • Logs en temps réel : journalctl -u $SERVICE_NAME -f"
print_status "  • Redémarrer : systemctl restart $SERVICE_NAME"
print_status "  • Arrêter : systemctl stop $SERVICE_NAME"
print_status ""
print_status "🔧 URL pour n8n : http://localhost:8000/chunk"