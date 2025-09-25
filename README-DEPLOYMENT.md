# 🚀 Déploiement Docker - Legal Document Chunking API

## 📋 Prérequis

- Docker et Docker Compose installés
- Réseaux Docker `docker_frontend` et `docker_backend` créés
- Traefik configuré avec résolveur Cloudflare (pour SSL automatique)

## 🛠️ Installation

### Première installation

```bash
# Cloner le repository
git clone https://github.com/SebWell/legal-document-chunking.git
cd legal-document-chunking

# Démarrer l'API
docker compose -f docker-compose.chunking.yml up -d --build
```

### 🔄 Mise à jour

```bash
# Pull des dernières modifications
git pull origin main

# Redémarrer avec la nouvelle version
docker compose -f docker-compose.chunking.yml up -d --build
```

### ⚡ Commandes utiles

```bash
# Voir les logs
docker compose -f docker-compose.chunking.yml logs -f

# Arrêter le service
docker compose -f docker-compose.chunking.yml down

# Redémarrer le service
docker compose -f docker-compose.chunking.yml restart

# Status du conteneur
docker compose -f docker-compose.chunking.yml ps
```

## 🌐 URLs d'accès

- **API** : https://chunk.chantierdoc.com/
- **Documentation interactive** : https://chunk.chantierdoc.com/docs
- **Health check** : https://chunk.chantierdoc.com/health
- **OpenAPI spec** : https://chunk.chantierdoc.com/openapi.json

## 🔧 Configuration n8n

Une fois l'API déployée, configurez votre nœud HTTP Request dans n8n :

**URL** : `https://chunk.chantierdoc.com/chunk`
**Méthode** : `POST`
**Headers** :
```json
{
  "Content-Type": "application/json"
}
```

**Body** :
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

**⚠️ Nouveaux champs obligatoires v2.1** :
- `userId` : Identifiant unique de l'utilisateur pour traçabilité
- `projectId` : Identifiant unique du projet pour organisation

## 🎯 Fonctionnalités Version 2.1

### ✨ Nouvelles fonctionnalités
- **Métadonnées contextuelles complètes** - Extraction automatique titre, date, parties, localisation
- **7 types de documents** supportés (VEFA, CCTP, Baux, Actes notariés, etc.)
- **ID standardisés** - Format AAAAMMJJHHMMSSXXX pour traçabilité
- **Références sources professionnelles** - Format optimisé RAG sans numéros internes
- **Traçabilité utilisateur/projet** - userId/projectId dans chaque chunk
- **Structure JSON enrichie** - Familles content/metadata/document_info

### 📊 Performance v2.1
- **12,5%** de chunks de faible qualité (maintenu)
- **100%** contexte documentaire préservé
- **100%** métadonnées extraites automatiquement
- **Nouveau** : traçabilité complète utilisateur/projet

## 🔒 Sécurité et Performance

### Sécurité
- ✅ Conteneur non-root
- ✅ SSL automatique via Cloudflare
- ✅ Rate limiting via Traefik
- ✅ CORS configuré pour n8n

### Performance
- ✅ Health checks automatiques
- ✅ Ressources limitées (1GB RAM max)
- ✅ Restart automatique en cas de problème
- ✅ Monitoring intégré

## 🐛 Dépannage

### Vérifier l'état du service
```bash
curl -f https://chunk.chantierdoc.com/health
```

### Consulter les logs
```bash
docker logs legal-document-chunking --tail 50 -f
```

### Test de l'API
```bash
curl -X POST "https://chunk.chantierdoc.com/chunk" \
  -H "Content-Type: application/json" \
  -d '{
    "extractedText": "Article 1. Test de chunking pour document juridique.",
    "userId": "test-user-123",
    "projectId": "test-project-456",
    "options": {"target_chunk_size": 60, "overlap_size": 15}
  }'
```

## 📈 Monitoring

L'API expose automatiquement :
- Endpoint `/health` pour les health checks
- Métriques de performance dans les logs
- Temps de traitement par requête
- Statistiques de qualité des chunks

---

🚀 **Déploiement en une commande - Mises à jour automatiques !**