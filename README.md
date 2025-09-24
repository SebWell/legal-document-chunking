# Legal Document Chunking API

API FastAPI pour le chunking intelligent de documents juridiques français, optimisée pour le secteur de la construction.

## 🎯 Objectif

Remplacer un système JavaScript n8n produisant 88% de chunks de faible qualité par une solution Python atteignant <20% de chunks de faible qualité.

**Résultats obtenus** : 12,5% de chunks de faible qualité (amélioration de 85,8% !)

## 🏗️ Secteur ciblé

- Contrats de construction
- CCTP (Cahiers des Clauses Techniques Particulières)
- Devis et factures
- Permis de construire
- Baux commerciaux
- Rapports d'expertise

## 🚀 Installation

### ⚡ Déploiement Docker (recommandé)

```bash
# Cloner et déployer en une commande
git clone https://github.com/SebWell/legal-document-chunking.git
cd legal-document-chunking
docker compose -f docker-compose.chunking.yml up -d --build
```

**URL** : https://chunk.chantierdoc.com/

### 🛠️ Déploiement VPS classique

```bash
# Copier les fichiers sur votre VPS
scp main.py requirements.txt deploy.sh user@votre-vps:/tmp/

# Se connecter et déployer
ssh user@votre-vps
cd /tmp
sudo chmod +x deploy.sh
sudo ./deploy.sh
```

### 💻 Installation locale

```bash
# Créer un environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'API
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 📡 API Endpoints

### POST `/chunk`

Chunking intelligent d'un document.

**Payload** :
```json
{
  "text": "Votre texte de document juridique...",
  "target_size": 60,
  "overlap": 15
}
```

**Réponse** :
```json
{
  "chunks": [
    "Premier chunk de texte...",
    "Deuxième chunk de texte..."
  ],
  "total_chunks": 12,
  "quality_metrics": {
    "low_quality_chunks": 1,
    "percentage": 8.3
  }
}
```

### GET `/health`

Vérification de l'état de l'API.

### GET `/docs`

Documentation interactive Swagger.

## 🔧 Configuration n8n

**URL** : `http://localhost:8000/chunk`

**Configuration du nœud HTTP Request** :
- Méthode : POST
- URL : http://localhost:8000/chunk
- Body :
```json
{
  "text": "{{$json.extractedText}}",
  "target_size": 60,
  "overlap": 15
}
```

## 🎯 Fonctionnalités

### Chunking Intelligent
- Segmentation basée sur les phrases
- Respect des structures juridiques
- Préservation du contexte avec overlap
- Adaptation selon le type de document

### Reconnaissance de Patterns Juridiques
- Clauses contractuelles
- Références légales
- Montants et dates
- Obligations et responsabilités
- Terminologie du bâtiment

### Métriques de Qualité
- Détection des chunks trop courts
- Validation de la cohérence
- Calcul du pourcentage de qualité
- Logging détaillé

## 📊 Performance

| Métrique | Ancien système | Nouveau système | Amélioration |
|----------|----------------|-----------------|--------------|
| Chunks de faible qualité | 88% | 12,5% | 85,8% |
| Qualité moyenne | 12% | 87,5% | +629% |
| Temps de traitement | Variable | ~100ms | Optimisé |

## 🛠️ Gestion du Service

```bash
# Statut du service
systemctl status legal-chunking-api

# Logs en temps réel
journalctl -u legal-chunking-api -f

# Redémarrer le service
systemctl restart legal-chunking-api

# Arrêter le service
systemctl stop legal-chunking-api
```

## 🔒 Sécurité

- CORS configuré pour n8n
- Validation des données d'entrée avec Pydantic
- Logs sécurisés sans exposition de données
- Service utilisateur non-privilégié (www-data)

## 📝 Licence

MIT License

## 🤝 Contribution

Les contributions sont les bienvenues ! Veuillez créer une issue ou une pull request.

## 📞 Support

Pour toute question ou problème, créez une issue sur ce repository.