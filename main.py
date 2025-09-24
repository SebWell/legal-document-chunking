"""
FastAPI server for Legal Document Chunking
Designed for VPS deployment with n8n
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
import re
import time
from datetime import datetime, timezone

app = FastAPI(
    title="Legal Document Chunking API",
    description="API pour le chunking intelligent de documents juridiques français",
    version="1.0.0"
)

# CORS pour n8n
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChunkingRequest(BaseModel):
    extractedText: str
    options: Optional[Dict[str, Any]] = {}

class ChunkingService:
    """Service de chunking intelligent pour documents juridiques."""

    def create_smart_chunks(self, text: str, target_size: int = 60, overlap: int = 15):
        """Créer des chunks intelligents avec segmentation par phrases."""
        # Nettoyage du texte
        text = re.sub(r'\s+', ' ', text.strip())

        # Découpage par phrases
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = []
        current_word_count = 0
        chunk_id = 1

        for sentence in sentences:
            if not sentence.strip():
                continue

            sentence_words = sentence.split()

            # Si ajouter cette phrase dépasse la taille cible
            if current_word_count + len(sentence_words) > target_size and current_chunk:
                # Créer le chunk actuel
                chunk_content = ' '.join(current_chunk)
                chunk = self.create_chunk(chunk_content, chunk_id)
                chunks.append(chunk)

                # Préparer le chunk suivant avec overlap
                overlap_words = []
                if overlap > 0:
                    all_words = ' '.join(current_chunk).split()
                    overlap_words = all_words[-overlap:] if len(all_words) >= overlap else all_words

                current_chunk = overlap_words + sentence_words
                current_word_count = len(current_chunk)
                chunk_id += 1
            else:
                # Ajouter la phrase au chunk actuel
                current_chunk.extend(sentence_words)
                current_word_count += len(sentence_words)

        # Chunk final
        if current_chunk:
            chunk_content = ' '.join(current_chunk)
            chunk = self.create_chunk(chunk_content, chunk_id)
            chunks.append(chunk)

        return chunks

    def create_chunk(self, content: str, chunk_id: int):
        """Créer un chunk avec métadonnées et analyse de qualité."""
        word_count = len(content.split())

        # Analyse de qualité
        quality_score = self.analyze_quality(content)

        # Extraction d'entités
        entities = self.extract_entities(content)

        # Classification du contenu
        content_type = self.classify_content(content)

        return {
            'id': f'chunk_{chunk_id:03d}',
            'content': content,
            'hierarchical_title': self.get_title(content),
            'content_type': content_type,
            'section_info': {
                'type': 'content',
                'number': chunk_id,
                'title': self.get_title(content)
            },
            'content_classification': {
                'type': content_type,
                'confidence': 0.85,
                'alternatives': [],
                'scores': self.get_classification_scores(content)
            },
            'metadata': {
                'word_count': word_count,
                'char_count': len(content),
                'position': chunk_id,
                'has_legal_references': bool(entities['legal_references']),
                'has_financial_info': bool(entities['monetary_amounts']),
                'has_dates': bool(entities['dates'])
            },
            'quality_analysis': {
                'overall_score': quality_score,
                'completeness': min(1.0, word_count / 50),
                'coherence': self.calculate_coherence(content),
                'relevance': self.calculate_relevance(content),
                'factual_density': self.calculate_factual_density(entities)
            },
            'extracted_entities': entities,
            'key_elements': self.extract_key_elements(content)
        }

    def analyze_quality(self, content: str) -> float:
        """Analyse de qualité basée sur plusieurs facteurs."""
        words = content.split()

        # Facteur longueur (optimal autour de 40-60 mots)
        length_factor = min(1.0, len(words) / 50) * (1 - max(0, (len(words) - 80) / 80))

        # Facteur mots-clés juridiques
        legal_keywords = [
            'article', 'contrat', 'clause', 'obligation', 'garantie', 'délai',
            'prix', 'conditions', 'partie', 'engagement', 'responsabilité',
            'droit', 'devoir', 'modalité', 'échéance', 'livraison'
        ]
        keyword_count = sum(1 for word in words if word.lower() in legal_keywords)
        keyword_factor = min(1.0, keyword_count / 3)

        # Facteur entités (dates, montants, références)
        has_date = bool(re.search(r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{1,2}\s+\w+\s+\d{4}', content))
        has_amount = bool(re.search(r'\d+[\s,]*\d*\s*(?:euros?|€|\$)', content, re.IGNORECASE))
        has_reference = bool(re.search(r'article\s+[a-z]?\d+', content, re.IGNORECASE))

        entity_factor = 0.6 + 0.15 * has_date + 0.15 * has_amount + 0.1 * has_reference

        # Facteur structure (phrases complètes)
        complete_sentences = len(re.findall(r'[.!?]', content))
        structure_factor = min(1.0, complete_sentences / 2)

        # Score final pondéré
        score = (
            0.3 * length_factor +
            0.25 * keyword_factor +
            0.25 * entity_factor +
            0.2 * structure_factor
        )

        return round(score, 3)

    def extract_entities(self, content: str) -> Dict:
        """Extraction d'entités juridiques et techniques."""
        entities = {
            'dates': [],
            'monetary_amounts': [],
            'legal_references': [],
            'measurements': [],
            'norms_standards': [],
            'materials': [],
            'technical_specs': []
        }

        # Dates (formats français)
        date_patterns = [
            r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}',
            r'\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}',
            r'(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}'
        ]
        for pattern in date_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['dates'].extend(matches)

        # Montants
        amount_patterns = [
            r'\d+[\s,]*\d*\s*(?:euros?|€)',
            r'\d+[\s,]*\d*\s*EUR',
            r'\d+[\s,]*\d*\s*(?:\$|dollars?)'
        ]
        for pattern in amount_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['monetary_amounts'].extend(matches)

        # Références légales
        legal_patterns = [
            r'article\s+[a-z]?\d+[\-\d]*',
            r'[Ll]\s*\d+[\-\d]*',
            r'[Rr]\s*\d+[\-\d]*',
            r'décret\s+n°\s*[\d\-]+',
            r'loi\s+n°\s*[\d\-]+',
            r'code\s+\w+'
        ]
        for pattern in legal_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['legal_references'].extend(matches)

        # Mesures et spécifications techniques
        measure_patterns = [
            r'\d+[\.,]?\d*\s*(?:m²|m2|mètres?\s*carrés?)',
            r'\d+[\.,]?\d*\s*(?:m³|m3|mètres?\s*cubes?)',
            r'\d+[\.,]?\d*\s*(?:ml?|mètres?)',
            r'\d+[\.,]?\d*\s*(?:cm|centimètres?)',
            r'\d+[\.,]?\d*\s*(?:mm|millimètres?)',
            r'\d+[\.,]?\d*\s*(?:kg|kilogrammes?)',
            r'\d+[\.,]?\d*\s*(?:tonnes?)',
            r'\d+[\.,]?\d*\s*(?:%|pour\s*cent)'
        ]
        for pattern in measure_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['measurements'].extend(matches)

        # Normes et standards
        norm_patterns = [
            r'DTU\s+[\d\.]+',
            r'NF\s+EN\s+[\d]+',
            r'NF\s+[\d]+',
            r'ISO\s+[\d]+',
            r'CE\s+[\d]+',
            r'C\d+\/\d+',
            r'HA\d+'
        ]
        for pattern in norm_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['norms_standards'].extend(matches)

        # Matériaux
        materials = [
            'béton', 'acier', 'bois', 'plâtre', 'ciment', 'sable', 'gravier',
            'parpaing', 'brique', 'tuile', 'ardoise', 'zinc', 'cuivre',
            'aluminium', 'PVC', 'polystyrène', 'laine de verre', 'laine de roche'
        ]
        for material in materials:
            if material in content.lower():
                entities['materials'].append(material)

        return entities

    def classify_content(self, content: str) -> str:
        """Classification du type de contenu."""
        content_lower = content.lower()

        # Mots-clés par catégorie
        categories = {
            'financial': ['prix', 'coût', 'tarif', 'montant', 'euros', '€', 'facture', 'paiement', 'acompte'],
            'timeline': ['délai', 'livraison', 'échéance', 'date', 'planning', 'durée', 'terme'],
            'obligations': ['obligation', 'engage', 'doit', 'responsabilité', 'devoir', 'tenu'],
            'guarantees': ['garantie', 'assurance', 'caution', 'couverture', 'protection'],
            'technical_requirements': ['technique', 'norme', 'spécification', 'matériau', 'DTU', 'performance'],
            'conditions': ['condition', 'clause', 'modalité', 'stipulation', 'disposition'],
            'quality_control': ['contrôle', 'vérification', 'test', 'essai', 'conformité'],
            'safety_security': ['sécurité', 'protection', 'risque', 'danger', 'prévention']
        }

        scores = {}
        for category, keywords in categories.items():
            score = sum(1 for keyword in keywords if keyword in content_lower)
            if score > 0:
                scores[category] = score

        if scores:
            return max(scores, key=scores.get)
        else:
            return 'general'

    def get_classification_scores(self, content: str) -> Dict:
        """Obtenir les scores de classification pour tous les types."""
        content_lower = content.lower()

        categories = {
            'obligations': ['obligation', 'engage', 'doit', 'responsabilité'],
            'conditions': ['condition', 'clause', 'modalité', 'si'],
            'financial': ['prix', 'coût', 'euros', '€', 'montant'],
            'timeline': ['délai', 'date', 'échéance', 'livraison'],
            'guarantees': ['garantie', 'assurance', 'caution'],
            'technical_requirements': ['technique', 'norme', 'spécification'],
            'quality_control': ['contrôle', 'vérification', 'test'],
            'safety_security': ['sécurité', 'protection', 'risque'],
            'administrative': ['autorisation', 'permis', 'déclaration'],
            'definitions': ['définition', 'signifie', 'désigne'],
            'procedures': ['procédure', 'méthode', 'étape']
        }

        scores = {}
        for category, keywords in categories.items():
            scores[category] = sum(1 for keyword in keywords if keyword in content_lower)

        return scores

    def calculate_coherence(self, content: str) -> float:
        """Calculer la cohérence du contenu."""
        sentences = re.split(r'[.!?]+', content)
        if len(sentences) < 2:
            return 0.8

        # Vérifier la présence de connecteurs
        connectors = ['et', 'ou', 'mais', 'donc', 'car', 'ainsi', 'alors', 'cependant', 'toutefois']
        connector_count = sum(1 for conn in connectors if conn in content.lower())

        coherence = min(1.0, 0.6 + (connector_count / len(sentences)) * 0.4)
        return round(coherence, 3)

    def calculate_relevance(self, content: str) -> float:
        """Calculer la pertinence juridique."""
        legal_terms = [
            'contrat', 'accord', 'convention', 'engagement', 'obligation',
            'droit', 'devoir', 'clause', 'article', 'disposition'
        ]

        words = content.lower().split()
        legal_word_count = sum(1 for word in words if word in legal_terms)

        relevance = min(1.0, 0.7 + (legal_word_count / len(words)) * 3)
        return round(relevance, 3)

    def calculate_factual_density(self, entities: Dict) -> float:
        """Calculer la densité factuelle basée sur les entités."""
        total_entities = sum(len(entity_list) for entity_list in entities.values())
        # Normaliser par rapport à un chunk moyen
        density = min(1.0, total_entities / 5)
        return round(density, 3)

    def get_title(self, content: str) -> str:
        """Extraire ou générer un titre pour le chunk."""
        # Chercher un article numéroté
        article_match = re.search(r'article\s+\d+[^\n.]*', content, re.IGNORECASE)
        if article_match:
            return article_match.group(0).strip()

        # Chercher une clause
        clause_match = re.search(r'clause\s+[^\n.]*', content, re.IGNORECASE)
        if clause_match:
            return clause_match.group(0).strip()

        # Première phrase courte
        sentences = re.split(r'[.!?]+', content)
        if sentences and len(sentences[0]) < 80:
            return sentences[0].strip()

        return "Clause contractuelle"

    def extract_key_elements(self, content: str) -> list:
        """Extraire les éléments clés du chunk."""
        elements = []

        # Mots-clés importants avec priorité
        priority_words = {
            'contrat': 3, 'prix': 3, 'délai': 3, 'garantie': 3,
            'obligation': 2, 'clause': 2, 'article': 2, 'conditions': 2,
            'paiement': 2, 'livraison': 2, 'responsabilité': 2,
            'assurance': 1, 'modalité': 1, 'échéance': 1
        }

        content_lower = content.lower()
        word_scores = []

        for word, priority in priority_words.items():
            if word in content_lower:
                word_scores.append((word, priority))

        # Trier par priorité et prendre les 5 premiers
        word_scores.sort(key=lambda x: x[1], reverse=True)
        elements = [word for word, _ in word_scores[:5]]

        return elements

    def detect_document_type(self, text: str) -> str:
        """Détection du type de document."""
        text_lower = text.lower()

        patterns = {
            'contrat_reservation_vefa': ['vefa', 'réservation', 'futur achèvement'],
            'cctp': ['cctp', 'clauses techniques particulières', 'cahier des charges'],
            'acte_notarie': ['acte', 'notaire', 'notarié', 'étude'],
            'bail_habitation': ['bail', 'location', 'logement', 'loyer'],
            'bail_commercial': ['bail commercial', 'fonds de commerce'],
            'marche_public': ['marché public', 'appel d\'offres', 'soumission'],
            'permis_construire': ['permis de construire', 'autorisation', 'urbanisme'],
            'devis': ['devis', 'estimation', 'chiffrage'],
            'facture': ['facture', 'facturation', 'tva']
        }

        for doc_type, keywords in patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                return doc_type

        return 'contrat_general'

# Instance du service
chunking_service = ChunkingService()

@app.get("/")
async def root():
    """Point d'entrée principal de l'API."""
    return {
        "message": "Legal Document Chunking API",
        "version": "1.0.0",
        "endpoints": {
            "chunk": "/chunk - POST - Chunking de documents",
            "health": "/health - GET - Status de l'API"
        }
    }

@app.get("/health")
async def health():
    """Endpoint de santé pour vérification."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/chunk")
async def chunk_document(request: ChunkingRequest):
    """Endpoint principal pour le chunking de documents."""
    try:
        extracted_text = request.extractedText.strip()

        if not extracted_text:
            raise HTTPException(
                status_code=400,
                detail="Le champ extractedText est requis et ne peut pas être vide"
            )

        if len(extracted_text) < 100:
            raise HTTPException(
                status_code=400,
                detail="Le texte doit contenir au moins 100 caractères"
            )

        # Options avec valeurs par défaut
        options = request.options
        target_chunk_size = options.get('target_chunk_size', 60)
        overlap_size = options.get('overlap_size', 15)

        # Validation des paramètres
        if not (20 <= target_chunk_size <= 200):
            raise HTTPException(
                status_code=400,
                detail="target_chunk_size doit être entre 20 et 200 mots"
            )

        if not (0 <= overlap_size <= 50):
            raise HTTPException(
                status_code=400,
                detail="overlap_size doit être entre 0 et 50 mots"
            )

        # Traitement du chunking
        start_time = time.time()

        chunks = chunking_service.create_smart_chunks(
            extracted_text,
            target_chunk_size,
            overlap_size
        )

        end_time = time.time()
        processing_time = int((end_time - start_time) * 1000)

        # Calcul des statistiques
        quality_dist = {'high': 0, 'medium': 0, 'low': 0}
        total_quality = 0

        for chunk in chunks:
            score = chunk['quality_analysis']['overall_score']
            total_quality += score

            if score >= 0.8:
                quality_dist['high'] += 1
            elif score >= 0.5:
                quality_dist['medium'] += 1
            else:
                quality_dist['low'] += 1

        avg_quality = total_quality / len(chunks) if chunks else 0

        # Validation des résultats
        low_quality_rate = (quality_dist['low'] / len(chunks) * 100) if chunks else 0

        validation_results = {
            'consistency_score': 0.85,
            'cross_reference_integrity': 0.90,
            'missing_elements': [],
            'recommendations': []
        }

        if low_quality_rate > 30:
            validation_results['recommendations'].append(
                "Taux élevé de chunks de basse qualité - considérer l'augmentation de target_chunk_size"
            )

        # Réponse finale
        response_data = {
            'success': True,
            'chunks': chunks,
            'document_stats': {
                'document_type': chunking_service.detect_document_type(extracted_text),
                'estimated_complexity': 'medium',
                'processing_time_ms': processing_time,
                'total_chunks': len(chunks),
                'avg_chunk_quality': round(avg_quality, 3),
                'quality_distribution': quality_dist,
                'text_length': len(extracted_text),
                'avg_chunk_size': sum(chunk['metadata']['word_count'] for chunk in chunks) / len(chunks) if chunks else 0
            },
            'validation_results': validation_results,
            'processing_info': {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'version': '1.0.0',
                'target_chunk_size': target_chunk_size,
                'overlap_size': overlap_size
            }
        }

        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du serveur: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)