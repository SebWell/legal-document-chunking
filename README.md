# Legal Document Chunking API

API FastAPI pour le chunking intelligent de documents juridiques français avec métadonnées contextuelles complètes, optimisée pour le secteur de la construction et l'intégration RAG.

## 🎯 Objectif

Remplacer un système JavaScript n8n produisant 88% de chunks de faible qualité par une solution Python atteignant <20% de chunks de faible qualité avec préservation du contexte documentaire.

**Résultats obtenus** : 12,5% de chunks de faible qualité (amélioration de 85,8% !) + contexte complet préservé dans chaque chunk

## 🏗️ Types de documents supportés

### 📋 Détection automatique de 7 types :
- **Contrats VEFA** - Vente en l'État Futur d'Achèvement
- **CCTP** - Cahiers des Clauses Techniques Particulières
- **Baux d'habitation** - Contrats de location résidentielle
- **Baux commerciaux** - Contrats de location professionnelle
- **Actes notariés** - Ventes, acquisitions immobilières
- **Permis de construire** - Autorisations d'urbanisme
- **Devis** - Estimations et chiffrages travaux

### 🔍 Extraction spécialisée par type :
- **Parties contractuelles** adaptées (réservant/réservataire, bailleur/locataire, etc.)
- **Dates clés** contextuelles (signature, livraison, échéances)
- **Références légales** spécifiques au domaine
- **Montants financiers** et conditions de paiement
- **Localisation** et descriptifs techniques

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
  "extractedText": "Votre texte de document juridique...",
  "userId": "uuid-user-123",
  "projectId": "uuid-project-456",
  "options": {
    "target_chunk_size": 60,
    "overlap_size": 15
  }
}
```

**Réponse** :
```json
{
  "success": true,
  "chunks": [
    {
      "content": {
        "text": "Premier chunk de texte...",
        "chunk_id": "chunk_001"
      },
      "metadata": {
        "word_count": 45,
        "quality_score": 0.87,
        "content_type": "legal_clause",
        "entities": {...}
      },
      "document_info": {
        "document_id": "20120915120000429",
        "title": "CONTRAT DE RESERVATION VEFA",
        "date": "15/09/2012",
        "parties": {
          "reservant": "SCCV LA VALLEE MONTEVRAIN",
          "reservataire": "[Réservataire]"
        },
        "project": "LE NEST",
        "source": "CONTRAT DE RESERVATION VEFA - Projet LE NEST (15/09/2012)"
      },
      "userId": "uuid-user-123",
      "projectId": "uuid-project-456"
    }
  ],
  "document_stats": {
    "total_chunks": 12,
    "avg_chunk_quality": 0.875,
    "document_info": {...}
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
- Headers :
```json
{
  "Content-Type": "application/json"
}
```
- Body :
```json
{
  "extractedText": "{{$json.extractedText}}",
  "userId": "{{$json.userId}}",
  "projectId": "{{$json.projectId}}",
  "options": {
    "target_chunk_size": 60,
    "overlap_size": 15
  }
}
```

**⚠️ Champs obligatoires** :
- `userId` : Identifiant unique de l'utilisateur
- `projectId` : Identifiant unique du projet
- `extractedText` : Texte du document à chunker

## 🎯 Fonctionnalités

### 🧠 Chunking Intelligent
- Segmentation basée sur les phrases avec contexte sémantique
- Respect des structures juridiques (articles, clauses, tableaux)
- Préservation du contexte avec overlap intelligent
- Adaptation automatique selon le type de document

### 📋 Extraction de Métadonnées Avancées
- **Identification automatique** de 7 types de documents juridiques
- **Extraction des parties** (réservant/réservataire, bailleur/locataire, etc.)
- **Dates principales** (signature, création, échéances)
- **Localisation** et projets immobiliers
- **ID standardisé** pour traçabilité complète

### 🔍 Reconnaissance de Patterns Juridiques
- Clauses contractuelles et articles de loi
- Références légales (Code civil, CCH, etc.)
- Montants financiers et échéanciers
- Obligations et responsabilités des parties
- Terminologie spécialisée du bâtiment

### ⚡ Optimisation RAG
- **Structure JSON optimisée** pour l'intégration RAG
- **Contexte documentaire complet** dans chaque chunk
- **Références sources professionnelles** sans numéros internes
- **Traçabilité utilisateur/projet** pour chaque chunk
- **Métadonnées enrichies** (entités, qualité, classification)

### 📊 Métriques de Qualité
- Analyse multi-facteurs (complétude, cohérence, densité)
- Score de qualité par chunk (0.0 à 1.0)
- Distribution statistique des performances
- Validation automatique des résultats

## 📊 Performance

| Métrique | Ancien système | Nouveau système v2.1 | Amélioration |
|----------|----------------|----------------------|--------------|
| Chunks de faible qualité | 88% | 12,5% | **85,8%** |
| Qualité moyenne | 12% | 87,5% | **+629%** |
| Temps de traitement | Variable | ~100ms | **Optimisé** |
| Contexte préservé | ❌ 0% | ✅ 100% | **Nouveau** |
| Métadonnées extraites | ❌ Aucune | ✅ Complètes | **Nouveau** |
| Traçabilité | ❌ Limitée | ✅ ID + User/Project | **Nouveau** |

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