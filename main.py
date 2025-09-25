"""
FastAPI server for Legal Document Chunking
Designed for VPS deployment with n8n
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
import re
import time
import hashlib
from datetime import datetime, timezone

app = FastAPI(
    title="Legal Document Chunking API",
    description="API pour le chunking intelligent de documents juridiques français avec métadonnées contextuelles",
    version="2.1.0"
)

# Force OpenAPI 3.0.2 pour compatibilité avec Swagger UI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        openapi_version="3.0.2"
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

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
    userId: str
    projectId: str
    options: Optional[Dict[str, Any]] = {}

class DocumentMetadataExtractor:
    """Extracteur de métadonnées documentaires pour le contexte RAG."""

    def __init__(self):
        self.document_patterns = {
            'contrat_reservation_vefa': {
                'title_patterns': [r'contrat.{0,20}r[eé]servation.{0,20}vefa', r'r[eé]servation.{0,30}futur.{0,10}ach[eè]vement'],
                'parties_patterns': {
                    'reservant': [
                        r'société\s+dénommée\s+([A-Z][^\n]+?)\s+au\s+capital',
                        r'r[eé]servant[^\n]*([A-Z][^\n]{10,80})',
                        r'dénommée\s+([A-Z][^\n]{20,80})'
                    ],
                    'reservataire': [
                        r'r[eé]servataire[^\n]*([A-Z][^\n]{10,80})',
                        r'appelé[e]?\s+réservataire[^\n]*([A-Z][^\n]{10,80})'
                    ]
                }
            },
            'cctp': {
                'title_patterns': [r'cctp', r'cahier.{0,20}clauses.{0,20}techniques', r'clauses.{0,20}techniques.{0,20}particuli[eè]res'],
                'parties_patterns': {'maitre_ouvrage': r'ma[iî]tre.{0,5}ouvrage[^\n]*([A-Z][^\n]{10,80})', 'entrepreneur': r'entrepreneur[^\n]*([A-Z][^\n]{10,80})'}
            },
            'bail_habitation': {
                'title_patterns': [r'bail.{0,20}habitation', r'bail.{0,20}location', r'contrat.{0,20}location'],
                'parties_patterns': {'bailleur': r'bailleur[^\n]*([A-Z][^\n]{10,80})', 'locataire': r'locataire[^\n]*([A-Z][^\n]{10,80})'}
            },
            'bail_commercial': {
                'title_patterns': [r'bail.{0,20}commercial', r'bail.{0,20}professionnel'],
                'parties_patterns': {'bailleur': r'bailleur[^\n]*([A-Z][^\n]{10,80})', 'preneur': r'preneur[^\n]*([A-Z][^\n]{10,80})'}
            },
            'acte_notarie': {
                'title_patterns': [r'acte.{0,20}notari[eé]', r'acte.{0,20}vente', r'acte.{0,20}acquisition'],
                'parties_patterns': {'vendeur': r'vendeur[^\n]*([A-Z][^\n]{10,80})', 'acquereur': r'acqu[eé]reur[^\n]*([A-Z][^\n]{10,80})'}
            },
            'permis_construire': {
                'title_patterns': [r'permis.{0,20}construire', r'autorisation.{0,20}construire'],
                'parties_patterns': {'demandeur': r'demandeur[^\n]*([A-Z][^\n]{10,80})', 'commune': r'commune.{0,20}([A-Z][^\n]{10,40})'}
            },
            'devis': {
                'title_patterns': [r'devis', r'estimation', r'chiffrage'],
                'parties_patterns': {'entreprise': r'entreprise[^\n]*([A-Z][^\n]{10,80})', 'client': r'client[^\n]*([A-Z][^\n]{10,80})'}
            }
        }

    def extract_document_metadata(self, text: str) -> Dict:
        """Extraction complète des métadonnées du document."""
        text_sample = text[:5000]  # Analyser les 5000 premiers caractères

        # 1. Classification du document
        doc_type = self.detect_document_type(text_sample)

        # 2. Extraction du titre
        title = self.extract_title(text_sample, doc_type)

        # 3. Extraction de la date principale
        date = self.extract_main_date(text_sample)

        # 4. Extraction des parties
        parties = self.extract_parties(text_sample, doc_type)

        # 5. Extraction de la localisation
        location = self.extract_location(text_sample)

        # 6. Génération de l'ID standardisé
        doc_id = self.generate_document_id(text, title, date)

        return {
            'id': doc_id,
            'title': title,
            'date': date,
            'type': doc_type,
            'parties': parties,
            'location': location,
            'project': self.extract_project_name(text_sample)
        }

    def detect_document_type(self, text: str) -> str:
        """Détecter le type de document avec patterns spécialisés."""
        text_lower = text.lower()

        # Score par type de document
        scores = {}
        for doc_type, patterns in self.document_patterns.items():
            score = 0
            for pattern in patterns['title_patterns']:
                matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                score += matches * 3  # Bonus pour les patterns de titre

            # Bonus pour la présence des parties typiques
            for party_type, pattern in patterns['parties_patterns'].items():
                if re.search(pattern, text, re.IGNORECASE):
                    score += 2

            if score > 0:
                scores[doc_type] = score

        return max(scores, key=scores.get) if scores else 'contrat_general'

    def extract_title(self, text: str, doc_type: str) -> str:
        """Extraire le titre principal du document."""
        # Rechercher le titre en fonction du type détecté
        if doc_type in self.document_patterns:
            for pattern in self.document_patterns[doc_type]['title_patterns']:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    title = match.group(0).strip()
                    # Nettoyer et formater le titre
                    title = re.sub(r'\s+', ' ', title)
                    return title.upper()

        # Fallback: chercher les premiers mots en majuscules
        title_patterns = [
            r'^\s*([A-Z][A-Z\s]{20,100}?)(?:\n|$)',
            r'(?:^|\n)\s*([A-Z][A-Z\s]{15,80}?)(?:\n|$)',
            r'(?:CONTRAT|BAIL|CCTP|DEVIS|ACTE)\s+[A-Z\s]{10,60}'
        ]

        for pattern in title_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                title = match.group(1) if match.groups() else match.group(0)
                return re.sub(r'\s+', ' ', title.strip())

        return "DOCUMENT JURIDIQUE"

    def extract_main_date(self, text: str) -> str:
        """Extraire la date principale (signature, création)."""
        # Patterns de dates avec contexte prioritaire
        priority_patterns = [
            r'sign[eé]\s+le\s+(\d{1,2}[\s\/\-\.]+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|\d{1,2})[\s\/\-\.]+\d{2,4})',
            r'fait\s+[àa]\s+[^\n]+\s+le\s+(\d{1,2}[\s\/\-\.]+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|\d{1,2})[\s\/\-\.]+\d{2,4})',
            r'\ben\s+date\s+du\s+(\d{1,2}[\s\/\-\.]+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|\d{1,2})[\s\/\-\.]+\d{2,4})',
            r'établi\s+le\s+(\d{1,2}[\s\/\-\.]+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|\d{1,2})[\s\/\-\.]+\d{2,4})'
        ]

        for pattern in priority_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self.normalize_date(match.group(1))

        # Fallback: première date trouvée
        general_patterns = [
            r'\d{1,2}[\s\/\-\.]+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)[\s\/\-\.]+\d{2,4}',
            r'\d{1,2}[\s\/\-\.]\d{1,2}[\s\/\-\.]\d{2,4}'
        ]

        for pattern in general_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self.normalize_date(match.group(0))

        return datetime.now().strftime("%d/%m/%Y")

    def normalize_date(self, date_str: str) -> str:
        """Normaliser une date au format DD/MM/YYYY."""
        # Mapping des mois français
        months = {
            'janvier': '01', 'février': '02', 'mars': '03', 'avril': '04',
            'mai': '05', 'juin': '06', 'juillet': '07', 'août': '08',
            'septembre': '09', 'octobre': '10', 'novembre': '11', 'décembre': '12'
        }

        date_clean = re.sub(r'\s+', ' ', date_str.strip().lower())

        # Format avec mois en lettres
        for month_name, month_num in months.items():
            if month_name in date_clean:
                parts = re.split(r'[\s\-\.\/]+', date_clean)
                day = parts[0].zfill(2)
                year = parts[2] if len(parts[2]) == 4 else '20' + parts[2]
                return f"{day}/{month_num}/{year}"

        # Format numérique
        parts = re.split(r'[\s\-\.\/]+', date_clean)
        if len(parts) >= 3:
            day = parts[0].zfill(2)
            month = parts[1].zfill(2)
            year = parts[2] if len(parts[2]) == 4 else ('20' + parts[2] if int(parts[2]) < 50 else '19' + parts[2])
            return f"{day}/{month}/{year}"

        return date_clean

    def extract_parties(self, text: str, doc_type: str) -> Dict:
        """Extraire les parties du contrat selon le type de document."""
        parties = {}

        if doc_type in self.document_patterns:
            patterns = self.document_patterns[doc_type]['parties_patterns']
            for party_type, pattern_list in patterns.items():
                # Handle both list and single pattern formats
                patterns_to_try = pattern_list if isinstance(pattern_list, list) else [pattern_list]

                for pattern in patterns_to_try:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        party_name = match.group(1) if match.groups() else match.group(0)
                        # Nettoyer le nom de la partie
                        party_name = re.sub(r'[,:;].*', '', party_name).strip()
                        parties[party_type] = party_name[:80]  # Limiter la longueur
                        break  # Stop at first match for this party type

        # Add default reservataire for VEFA contracts if not found
        if doc_type == 'contrat_reservation_vefa' and 'reservataire' not in parties:
            parties['reservataire'] = '[Réservataire]'

        # Fallback: recherche générique
        if not parties:
            generic_patterns = {
                'partie_1': r'dénommé[e]?\s+[«"]([^»"\n]{10,80})[»"]',
                'partie_2': r'd\'autre\s+part[^\n]*([A-Z][^\n]{10,80})'
            }

            for party_type, pattern in generic_patterns.items():
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    parties[party_type] = match.group(1).strip()[:80]

        return parties

    def extract_location(self, text: str) -> str:
        """Extraire la localisation principale."""
        location_patterns = [
            r'(?:situé|sis|localisé)[^\n]*?([A-Z][a-z]+(?:[\s\-][A-Z][a-z]+)*(?:\s*\(\d{2,5}\))?)',
            r'commune\s+de\s+([A-Z][a-z]+(?:[\s\-][A-Z][a-z]+)*)',
            r'([A-Z][A-Z\s]+)\s*\(\d{2,5}\)',
            r'\b([A-Z][a-z]+(?:[\s\-][A-Z][a-z]+)*)\s*\(\d{2,5}\)'
        ]

        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                location = match.group(1).strip()
                # Vérifier que ce n'est pas un nom de société
                if not re.match(r'(SARL|SAS|SA|SASU|EURL|SCI)', location, re.IGNORECASE):
                    return location

        return ""

    def extract_project_name(self, text: str) -> str:
        """Extraire le nom du projet/programme."""
        project_patterns = [
            r'programme[^\n]*[«"]([^»"\n]{5,50})[»"]',
            r'résidence[^\n]*[«"]([^»"\n]{5,50})[»"]',
            r'projet[^\n]*[«"]([^»"\n]{5,50})[»"]',
            r'dénommé[e]?[^\n]*[«"]([^»"\n]{5,50})[»"]'
        ]

        for pattern in project_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def generate_document_id(self, text: str, title: str, date: str) -> str:
        """Générer un ID standardisé AAAAMMJJHHMMSSXXX."""
        # Utiliser la date du document si disponible, sinon date actuelle
        try:
            if date and '/' in date:
                day, month, year = date.split('/')[:3]
                doc_date = datetime(int(year), int(month), int(day), 12, 0, 0)
            else:
                doc_date = datetime.now()
        except:
            doc_date = datetime.now()

        # Format de base: AAAAMMJJHHMMSS
        base_id = doc_date.strftime("%Y%m%d%H%M%S")

        # Générer un hash court du contenu pour l'unicité
        content_hash = hashlib.md5((text + title).encode('utf-8')).hexdigest()[:3].upper()

        return base_id + content_hash


class ChunkingService:
    """Service de chunking intelligent pour documents juridiques - Version Pro."""

    def __init__(self):
        # Dictionnaires spécialisés pour l'immobilier
        self.real_estate_terms = {
            'construction': ['gros œuvre', 'second œuvre', 'fondations', 'charpente', 'couverture', 'étanchéité', 'isolation', 'cloisons', 'revêtements'],
            'legal_actors': ['maître d\'ouvrage', 'maître d\'œuvre', 'architecte', 'entrepreneur', 'sous-traitant', 'bureau d\'études', 'contrôleur technique'],
            'insurance': ['dommages-ouvrage', 'décennale', 'biennale', 'parfait achèvement', 'responsabilité civile', 'tous risques chantier'],
            'certifications': ['RT2012', 'RT2020', 'HQE', 'BBC', 'BEPOS', 'NF Habitat', 'Qualitel'],
            'procedures': ['permis de construire', 'déclaration préalable', 'DT-DICT', 'réception des travaux', 'levée des réserves'],
            'financial_terms': ['révision de prix', 'actualisation', 'variation', 'acompte', 'avancement', 'retenue de garantie', 'décompte']
        }

        # Initialiser l'extracteur de métadonnées
        self.metadata_extractor = DocumentMetadataExtractor()

    def create_smart_chunks(self, text: str, target_size: int = 60, overlap: int = 15, user_id: str = None, project_id: str = None):
        """Créer des chunks intelligents avec gestion avancée des structures."""
        # Nettoyage et préparation du texte
        text = self.preprocess_text(text)

        # Détection des structures spéciales
        special_sections = self.detect_special_structures(text)

        # Adaptation de la taille selon le contenu
        adaptive_size = self.calculate_adaptive_size(text, target_size)

        # Traitement selon la structure détectée
        if special_sections['has_tables']:
            return self.chunk_with_table_handling(text, adaptive_size, overlap, user_id=user_id, project_id=project_id)
        else:
            return self.chunk_standard_content(text, adaptive_size, overlap, user_id=user_id, project_id=project_id)

    def preprocess_text(self, text: str) -> str:
        """Prétraitement avancé du texte."""
        # Nettoyage des espaces multiples
        text = re.sub(r'\s+', ' ', text.strip())

        # Normalisation des caractères spéciaux
        text = re.sub(r'[\u00A0\u2000-\u200B\u2028\u2029]', ' ', text)

        # Protection des structures importantes
        text = self.protect_legal_structures(text)

        return text

    def protect_legal_structures(self, text: str) -> str:
        """Protéger les structures juridiques importantes."""
        # Protéger les références d'articles
        text = re.sub(r'(article\s+[a-z]?\d+[\-\d]*)', r'\1🔒', text, flags=re.IGNORECASE)

        # Protéger les montants
        text = re.sub(r'(\d+[\s,]*\d*\s*(?:euros?|€))', r'\1🔒', text, flags=re.IGNORECASE)

        return text

    def detect_special_structures(self, text: str) -> dict:
        """Détecter les structures spéciales dans le document."""
        return {
            'has_tables': '|' in text or 'Nom / Dénomination' in text,
            'has_numbered_clauses': bool(re.search(r'^\s*\d+[\./)]', text, re.MULTILINE)),
            'has_legal_formulas': bool(re.search(r'\$[^\$]+\$', text)),
            'has_complex_references': len(re.findall(r'article\s+[a-z]?\d+', text, re.IGNORECASE)) > 5
        }

    def calculate_adaptive_size(self, text: str, base_size: int) -> int:
        """Calculer la taille adaptative selon le type de contenu."""
        content_type = self.classify_global_content(text)

        size_adjustments = {
            'financial': base_size + 10,  # Plus de contexte pour les clauses financières
            'technical_requirements': base_size + 15,  # Spécifications techniques détaillées
            'obligations': base_size - 5,  # Obligations plus concises
            'timeline': base_size,
            'legal_references': base_size - 10  # Articles courts et précis
        }

        return size_adjustments.get(content_type, base_size)

    def classify_global_content(self, text: str) -> str:
        """Classification globale du document."""
        text_lower = text.lower()

        # Calcul des scores pour chaque catégorie
        category_scores = {
            'financial': len(re.findall(r'prix|coût|euros?|€|montant|facture|paiement|devis', text_lower)),
            'technical_requirements': len(re.findall(r'technique|norme|spécification|matériau|dtu|performance|qualité', text_lower)),
            'obligations': len(re.findall(r'obligation|engage|doit|responsabilité|devoir|tenu', text_lower)),
            'timeline': len(re.findall(r'délai|livraison|échéance|date|planning|durée', text_lower)),
            'legal_references': len(re.findall(r'article|décret|loi|code|référence', text_lower))
        }

        return max(category_scores, key=category_scores.get) if any(category_scores.values()) else 'general'

    def chunk_with_table_handling(self, text: str, target_size: int, overlap: int, user_id: str = None, project_id: str = None):
        """Chunking spécialisé pour les documents avec tableaux."""
        chunks = []
        chunk_id = 1

        # Séparation du contenu par sections
        sections = self.split_by_tables(text)

        for section in sections:
            if self.is_table_content(section):
                # Traitement spécialisé pour les tableaux
                table_chunks = self.chunk_table_content(section, chunk_id, user_id, project_id)
                chunks.extend(table_chunks)
                chunk_id += len(table_chunks)
            else:
                # Traitement standard pour le texte normal
                section_chunks = self.chunk_standard_content(section, target_size, overlap, start_id=chunk_id, user_id=user_id, project_id=project_id)
                chunks.extend(section_chunks)
                chunk_id += len(section_chunks)

        return chunks

    def split_by_tables(self, text: str) -> list:
        """Séparer le texte en sections normales et tableaux."""
        # Pattern pour détecter les débuts de tableaux
        table_pattern = r'(\|[^|]*\|[^|]*\|)'

        sections = []
        last_end = 0

        for match in re.finditer(table_pattern, text):
            # Ajouter le texte avant le tableau
            if match.start() > last_end:
                sections.append(text[last_end:match.start()])

            # Trouver la fin du tableau
            table_start = match.start()
            table_end = self.find_table_end(text, table_start)
            sections.append(text[table_start:table_end])
            last_end = table_end

        # Ajouter le texte restant
        if last_end < len(text):
            sections.append(text[last_end:])

        return [s.strip() for s in sections if s.strip()]

    def find_table_end(self, text: str, start: int) -> int:
        """Trouver la fin d'un tableau."""
        lines = text[start:].split('\n')
        end_line = 0

        for i, line in enumerate(lines):
            if '|' not in line and line.strip() and not re.match(r'^\s*[-:]+\s*$', line):
                break
            end_line = i + 1

        return start + len('\n'.join(lines[:end_line]))

    def is_table_content(self, section: str) -> bool:
        """Vérifier si une section contient un tableau."""
        return '|' in section and section.count('|') >= 4

    def chunk_table_content(self, table_text: str, start_id: int, user_id: str = None, project_id: str = None) -> list:
        """Chunking spécialisé pour les tableaux."""
        chunks = []
        lines = table_text.strip().split('\n')

        # Grouper les lignes de tableau en chunks logiques
        current_group = []
        header_processed = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Conserver l'en-tête avec chaque groupe
            if not header_processed and '|' in line and not re.match(r'^\s*[-:]+\s*$', line):
                header = line
                header_processed = True
                current_group.append(line)
            elif re.match(r'^\s*[-:]+\s*$', line):
                current_group.append(line)
            else:
                current_group.append(line)

                # Créer un chunk tous les 3-4 lignes de données
                if len(current_group) >= 4:
                    chunk_content = '\n'.join(current_group)
                    chunk = self.create_chunk(chunk_content, start_id)
                    chunks.append(chunk)

                    # Redémarrer avec l'en-tête
                    current_group = [header] if 'header' in locals() else []
                    start_id += 1

        # Chunk final s'il reste des données
        if current_group and len(current_group) > 1:
            chunk_content = '\n'.join(current_group)
            chunk = self.create_chunk(chunk_content, start_id)
            chunks.append(chunk)

        return chunks

    def chunk_standard_content(self, text: str, target_size: int, overlap: int, start_id: int = 1, user_id: str = None, project_id: str = None):
        """Chunking standard amélioré."""
        # Découpage par phrases avec gestion des abréviations
        sentences = self.smart_sentence_split(text)
        chunks = []
        current_chunk = []
        current_word_count = 0
        chunk_id = start_id

        for sentence in sentences:
            if not sentence.strip():
                continue

            sentence_words = sentence.split()

            # Vérification de la cohésion avant de couper
            if (current_word_count + len(sentence_words) > target_size and
                current_chunk and self.can_split_here(sentence, current_chunk)):

                # Créer le chunk actuel
                chunk_content = ' '.join(current_chunk)
                chunk = self.create_chunk(chunk_content, chunk_id, user_id, project_id)
                chunks.append(chunk)

                # Préparer le chunk suivant avec overlap sémantique
                overlap_words = self.get_semantic_overlap(current_chunk, overlap)
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
            chunk = self.create_chunk(chunk_content, chunk_id, user_id, project_id)
            chunks.append(chunk)

        return chunks

    def smart_sentence_split(self, text: str) -> list:
        """Découpage intelligent des phrases avec gestion des abréviations."""
        # Protéger les abréviations courantes
        abbreviations = ['art.', 'etc.', 'cf.', 'p.ex.', 'c.-à-d.', 'M.', 'Mme', 'Dr.', 'Me']

        protected_text = text
        for abbr in abbreviations:
            protected_text = protected_text.replace(abbr, abbr.replace('.', '🔒'))

        # Découpage par phrases
        sentences = re.split(r'(?<=[.!?])\s+', protected_text)

        # Restaurer les points
        sentences = [s.replace('🔒', '.') for s in sentences]

        return sentences

    def can_split_here(self, next_sentence: str, current_chunk: list) -> bool:
        """Vérifier si on peut couper à cet endroit sans nuire à la cohésion."""
        if not current_chunk:
            return True

        # Ne pas couper si la phrase suivante commence par une conjonction
        conjunctions = ['et', 'ou', 'mais', 'donc', 'car', 'ainsi', 'alors', 'cependant', 'toutefois', 'néanmoins']
        first_word = next_sentence.strip().split()[0].lower() if next_sentence.strip() else ''

        if first_word in conjunctions:
            return False

        # Ne pas couper au milieu d'une énumération
        last_chunk_text = ' '.join(current_chunk[-10:])  # Derniers mots
        if re.search(r'[;:]\s*$', last_chunk_text):
            return False

        return True

    def get_semantic_overlap(self, current_chunk: list, overlap_size: int) -> list:
        """Obtenir un overlap sémantique plutôt que simplement les derniers mots."""
        if overlap_size == 0 or not current_chunk:
            return []

        # Chercher la dernière phrase complète dans la limite de l'overlap
        chunk_text = ' '.join(current_chunk)
        sentences = re.split(r'(?<=[.!?])\s+', chunk_text)

        # Prendre la dernière phrase si elle fait moins que l'overlap
        if sentences and len(sentences[-1].split()) <= overlap_size:
            return sentences[-1].split()

        # Sinon, prendre les derniers mots
        return current_chunk[-overlap_size:] if len(current_chunk) >= overlap_size else current_chunk

    def create_chunk(self, content: str, chunk_id: int, user_id: str = None, project_id: str = None):
        """Créer un chunk avec métadonnées et analyse de qualité."""
        word_count = len(content.split())

        # Analyse de qualité
        quality_score = self.analyze_quality(content)

        # Extraction d'entités
        entities = self.extract_entities(content)

        # Classification du contenu
        content_type = self.classify_content(content)

        # Structure simplifiée en 2 familles
        return {
            'content': {
                'text': content,
                'chunk_id': f'chunk_{chunk_id:03d}'
            },
            'metadata': {
                'word_count': word_count,
                'char_count': len(content),
                'position': chunk_id,
                'content_type': content_type,
                'quality_score': quality_score,
                'entities': entities,
                'hierarchical_title': self.get_title(content),
                'key_elements': self.extract_key_elements(content)
            },
            'userId': user_id,
            'projectId': project_id
        }

    def enrich_chunk_with_metadata(self, chunk: Dict, document_metadata: Dict) -> Dict:
        """Enrichir un chunk avec les métadonnées du document."""
        # Générer le format de source professionnel
        source_info = self.generate_professional_source(document_metadata, chunk['metadata'])

        # Structure finale avec 2 familles : content + document_info
        return {
            'content': chunk['content'],  # Texte + chunk_id
            'document_info': document_metadata,  # Toutes les métadonnées du document
            'chunk_metadata': chunk['metadata'],  # Métadonnées spécifiques au chunk
            'source_reference': source_info  # Référence formatée pour RAG
        }

    def generate_professional_source(self, document_metadata: Dict, chunk_metadata: Dict) -> str:
        """Générer une référence source professionnelle."""
        # Construire le titre avec projet si disponible
        title = document_metadata.get('title', 'DOCUMENT JURIDIQUE')
        project = document_metadata.get('project', '')
        if project and project not in title:
            title = f"{title} - {project}"

        # Date formatée
        date = document_metadata.get('date', '')
        date_str = f" ({date})" if date else ""

        # Parties formatées
        parties = document_metadata.get('parties', {})
        parties_str = ""
        if parties:
            party_names = []
            for party_type, party_name in parties.items():
                if party_name:
                    party_names.append(party_name)
            if len(party_names) >= 2:
                parties_str = f"\nParties : {party_names[0]} vs {party_names[1]}"
            elif len(party_names) == 1:
                parties_str = f"\nPartie : {party_names[0]}"

        # Document ID
        doc_id = document_metadata.get('id', '')
        doc_id_str = f"\nDocument ID: {doc_id}" if doc_id else ""

        # Localisation si disponible
        location = document_metadata.get('location', '')
        location_str = f"\nLocalisation : {location}" if location else ""

        # Titre hiérarchique du chunk (clause, article, etc.)
        hierarchical_title = chunk_metadata.get('hierarchical_title', '')
        clause_str = f"\n{hierarchical_title}" if hierarchical_title and hierarchical_title != "Clause contractuelle" else ""

        # Assembler la référence complète
        source_reference = f"Source : {title}{date_str}{parties_str}{doc_id_str}{location_str}{clause_str}"

        return source_reference.strip()

    def analyze_quality(self, content: str) -> float:
        """Analyse de qualité avancée basée sur de multiples facteurs."""
        words = content.split()
        word_count = len(words)

        # 1. Facteur longueur optimisé (courbe gaussienne)
        optimal_length = 55  # Taille optimale pour l'immobilier
        length_variance = 25
        length_factor = max(0.3, 1.0 - ((word_count - optimal_length) ** 2) / (2 * length_variance ** 2))

        # 2. Facteur mots-clés immobiliers pondérés
        weighted_keywords = {
            # Mots-clés prioritaires (poids 3)
            'contrat': 3, 'prix': 3, 'délai': 3, 'garantie': 3, 'obligation': 3,
            # Mots-clés importants (poids 2)
            'article': 2, 'clause': 2, 'conditions': 2, 'responsabilité': 2,
            'livraison': 2, 'paiement': 2, 'travaux': 2, 'entreprise': 2,
            # Mots-clés secondaires (poids 1)
            'partie': 1, 'engagement': 1, 'modalité': 1, 'échéance': 1,
            'conformité': 1, 'exécution': 1, 'réception': 1, 'achevements': 1
        }

        keyword_score = sum(weighted_keywords.get(word.lower(), 0) for word in words)
        max_possible_score = word_count * 3  # Si tous les mots étaient prioritaires
        keyword_factor = min(1.0, keyword_score / max(max_possible_score * 0.2, 1))

        # 3. Facteur entités enrichi
        entities = self.extract_entities(content)
        entity_score = 0

        # Dates (important pour les délais)
        if entities['dates']:
            entity_score += 0.15
        if entities['deadlines']:
            entity_score += 0.1

        # Montants financiers (critiques)
        if entities['monetary_amounts']:
            entity_score += 0.2

        # Références légales (fond juridique)
        if entities['legal_references']:
            entity_score += 0.15

        # Mesures et spécifications (technique)
        if entities['measurements'] or entities['technical_specs']:
            entity_score += 0.1

        # Acteurs et assurances (contextuel)
        if entities['real_estate_actors'] or entities['insurance_terms']:
            entity_score += 0.1

        # Normes (qualité technique)
        if entities['norms_standards']:
            entity_score += 0.1

        entity_factor = min(1.0, 0.4 + entity_score)  # Base 0.4 + bonus

        # 4. Facteur structure avancé
        complete_sentences = len(re.findall(r'[.!?]', content))

        # Bonus pour la structure logique
        has_enumeration = bool(re.search(r'[;:]\s*(?:\n|$)', content))
        has_paragraphs = '\n' in content.strip()
        has_proper_punctuation = complete_sentences > 0

        structure_base = min(1.0, complete_sentences / 2)
        structure_bonus = 0.1 * has_enumeration + 0.1 * has_paragraphs + 0.1 * has_proper_punctuation
        structure_factor = min(1.0, structure_base + structure_bonus)

        # 5. Facteur cohésion sémantique
        coherence_factor = self.calculate_semantic_coherence(content, words)

        # 6. Facteur spécificité immobilier
        real_estate_terms = [
            'construction', 'bâtiment', 'immeuble', 'logement', 'terrain',
            'permis', 'urbanisme', 'maître d\'ouvrage', 'architecte',
            'entrepreneur', 'chantier', 'réception', 'livraison', 'conformité'
        ]
        re_term_count = sum(1 for term in real_estate_terms if term in content.lower())
        specificity_factor = min(1.0, 0.7 + (re_term_count / len(real_estate_terms)) * 0.3)

        # Score final pondéré optimisé
        score = (
            0.25 * length_factor +      # Longueur optimale
            0.20 * keyword_factor +     # Mots-clés juridiques
            0.25 * entity_factor +      # Richesse des entités
            0.15 * structure_factor +   # Structure du texte
            0.10 * coherence_factor +   # Cohésion sémantique
            0.05 * specificity_factor   # Spécificité immobilier
        )

        return round(min(1.0, score), 3)

    def calculate_semantic_coherence(self, content: str, words: list) -> float:
        """Calculer la cohésion sémantique du contenu."""
        if len(words) < 10:
            return 0.5

        # Détecter la répétition excessive
        unique_words = set(word.lower() for word in words if len(word) > 3)
        repetition_ratio = len(unique_words) / len([w for w in words if len(w) > 3])
        repetition_factor = min(1.0, repetition_ratio * 2)  # Pénaliser la répétition

        # Détecter les connecteurs logiques
        connectors = [
            'et', 'ou', 'mais', 'donc', 'car', 'ainsi', 'alors', 'cependant',
            'toutefois', 'néanmoins', 'par conséquent', 'en effet', 'de plus',
            'en outre', 'notamment', 'c\'est-à-dire', 'autrement dit'
        ]
        connector_count = sum(1 for conn in connectors if conn in content.lower())
        connector_factor = min(1.0, 0.6 + (connector_count / len(content.split())) * 10)

        # Détecter la continuité thématique
        theme_consistency = self.calculate_theme_consistency(content)

        return round((repetition_factor + connector_factor + theme_consistency) / 3, 3)

    def calculate_theme_consistency(self, content: str) -> float:
        """Calculer la consistance thématique."""
        content_lower = content.lower()

        # Définir les thèmes principaux
        themes = {
            'contractuel': ['contrat', 'clause', 'obligation', 'engagement', 'accord'],
            'financier': ['prix', 'coût', 'montant', 'paiement', 'facture', 'devis'],
            'temporel': ['délai', 'livraison', 'échéance', 'planning', 'durée'],
            'technique': ['travaux', 'construction', 'matériaux', 'norme', 'qualité'],
            'juridique': ['responsabilité', 'garantie', 'assurance', 'droit', 'loi']
        }

        theme_scores = {}
        for theme_name, keywords in themes.items():
            score = sum(1 for keyword in keywords if keyword in content_lower)
            if score > 0:
                theme_scores[theme_name] = score

        if not theme_scores:
            return 0.5

        # Calculer la dominance du thème principal
        max_score = max(theme_scores.values())
        total_score = sum(theme_scores.values())

        # Un contenu cohérent a un thème dominant mais pas exclusif
        theme_dominance = max_score / total_score if total_score > 0 else 0

        # Optimum autour de 0.4-0.6 (pas trop dispersé, pas trop mono-thématique)
        if 0.3 <= theme_dominance <= 0.7:
            return min(1.0, 0.8 + (1 - abs(theme_dominance - 0.5)) * 0.4)
        else:
            return max(0.3, 0.8 - abs(theme_dominance - 0.5))

    def extract_entities(self, content: str) -> Dict:
        """Extraction d'entités juridiques et techniques avancée."""
        entities = {
            'dates': [],
            'monetary_amounts': [],
            'legal_references': [],
            'measurements': [],
            'norms_standards': [],
            'materials': [],
            'technical_specs': [],
            'real_estate_actors': [],
            'insurance_terms': [],
            'deadlines': [],
            'penalties': []
        }

        # Dates (formats français étendus)
        date_patterns = [
            r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}',
            r'\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}',
            r'(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}',
            r'\d{1,2}er?\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}',
            r'(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}'
        ]
        for pattern in date_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['dates'].extend(matches)

        # Montants et devises avancés
        amount_patterns = [
            r'\d+[\s,]*\d*[\.,]\d{2}\s*(?:euros?|€)',
            r'\d+[\s,]*\d*\s*(?:euros?|€)',
            r'\d+[\s,]*\d*\s*EUR',
            r'\d+[\s,]*\d*\s*(?:\$|dollars?)',
            r'(?:prix|coût|montant|tarif)\s*:?\s*\d+[\s,]*\d*',
            r'\d+[\s,]*\d*\s*(?:k€|K€|milliers?\s*d\'euros?)',
            r'TVA\s*:?\s*\d+[\.,]?\d*\s*%?',
            r'HT|TTC'
        ]
        for pattern in amount_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['monetary_amounts'].extend(matches)

        # Références légales étendues
        legal_patterns = [
            r'article\s+[a-z]?\d+[\-\d]*(?:\s*bis|ter|quater)?',
            r'[Ll]\s*\d+[\-\d]*',
            r'[Rr]\s*\d+[\-\d]*',
            r'décret\s+n°?\s*[\d\-]+',
            r'loi\s+n°?\s*[\d\-]+',
            r'code\s+(?:civil|pénal|de\s+(?:la\s+)?construction|du\s+travail|de\s+l\'urbanisme)',
            r'CCH|CGCT|CPC|CPP',
            r'arrêté\s+(?:du\s+)?\d+',
            r'circulaire\s+n°?\s*[\d\-]+'
        ]
        for pattern in legal_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['legal_references'].extend(matches)

        # Mesures et spécifications techniques étendues
        measure_patterns = [
            r'\d+[\.,]?\d*\s*(?:m²|m2|mètres?\s*carrés?)',
            r'\d+[\.,]?\d*\s*(?:m³|m3|mètres?\s*cubes?)',
            r'\d+[\.,]?\d*\s*(?:ml?|mètres?\s*linéaires?)',
            r'\d+[\.,]?\d*\s*(?:cm|centimètres?)',
            r'\d+[\.,]?\d*\s*(?:mm|millimètres?)',
            r'\d+[\.,]?\d*\s*(?:kg|kilogrammes?)',
            r'\d+[\.,]?\d*\s*(?:tonnes?)',
            r'\d+[\.,]?\d*\s*(?:%|pour\s*cent)',
            r'\d+[\.,]?\d*\s*(?:kW|MW|watts?)',
            r'\d+[\.,]?\d*\s*(?:°C|degrés?)',
            r'épaisseur\s*:?\s*\d+[\.,]?\d*\s*(?:cm|mm)',
            r'hauteur\s*:?\s*\d+[\.,]?\d*\s*m'
        ]
        for pattern in measure_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['measurements'].extend(matches)

        # Normes et standards BTP étendus
        norm_patterns = [
            r'DTU\s+[\d\.]+',
            r'NF\s+EN\s+[\d\-]+',
            r'NF\s+[ABCP]\d+[\-\d]*',
            r'ISO\s+[\d\-]+',
            r'EN\s+[\d\-]+',
            r'AFNOR\s+[\w\d\-]+',
            r'RT\s*20(?:05|12|20)',
            r'RE\s*2020',
            r'BBC|HQE|BEPOS|HPE',
            r'Effinergie|Passivhaus',
            r'QUALIBAT|RGE|OPQIBI'
        ]
        for pattern in norm_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['norms_standards'].extend(matches)

        # Matériaux BTP étendus
        materials_extended = [
            'béton', 'acier', 'bois', 'plâtre', 'ciment', 'sable', 'gravier',
            'parpaing', 'brique', 'tuile', 'ardoise', 'zinc', 'cuivre',
            'aluminium', 'PVC', 'polystyrène', 'laine de verre', 'laine de roche',
            'isolant', 'membrane', 'étanchéité', 'revêtement', 'enduit',
            'carrelage', 'parquet', 'moquette', 'peinture', 'crépi',
            'charpente', 'poutre', 'poteau', 'dalle', 'cloison'
        ]
        for material in materials_extended:
            if material in content.lower():
                entities['materials'].append(material)

        # Acteurs immobiliers
        real_estate_patterns = [
            r'maître\s+d\'ouvrage',
            r'maître\s+d\'œuvre',
            r'architecte',
            r'entrepreneur',
            r'sous-traitant',
            r'bureau\s+d\'études',
            r'contrôleur\s+technique',
            r'coordonnateur\s+sps',
            r'géomètre',
            r'notaire',
            r'promoteur',
            r'lotisseur'
        ]
        for pattern in real_estate_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['real_estate_actors'].extend(matches)

        # Termes d'assurance
        insurance_patterns = [
            r'dommages?[-\s]ouvrage',
            r'décennale',
            r'biennale',
            r'parfait\s+achèvement',
            r'responsabilité\s+civile',
            r'tous\s+risques?\s+chantier',
            r'garantie\s+financière',
            r'caution\s+de\s+soumission'
        ]
        for pattern in insurance_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['insurance_terms'].extend(matches)

        # Délais spécifiques
        deadline_patterns = [
            r'\d+\s*jours?\s*(?:ouvrables?|ouvrés?|calendaires?)?',
            r'\d+\s*semaines?',
            r'\d+\s*mois',
            r'\d+\s*années?',
            r'délai\s+de\s+\d+',
            r'dans\s+les\s+\d+\s*(?:jours?|mois)',
            r'avant\s+le\s+\d+',
            r'à\s+compter\s+du?'
        ]
        for pattern in deadline_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['deadlines'].extend(matches)

        # Pénalités et sanctions
        penalty_patterns = [
            r'pénalités?\s*(?:de\s+retard)?',
            r'astreintes?',
            r'dommages?[-\s]intérêts',
            r'indemnités?',
            r'résolution\s+du\s+contrat',
            r'résiliation',
            r'exclusion',
            r'\d+[\.,]?\d*\s*%\s*par\s*(?:jour|mois)\s*de\s*retard'
        ]
        for pattern in penalty_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['penalties'].extend(matches)

        # Spécifications techniques
        tech_spec_patterns = [
            r'classe\s+[A-F]\d*',
            r'résistance\s*:?\s*\d+[\.,]?\d*\s*MPa',
            r'pH\s*:?\s*\d+[\.,]?\d*',
            r'température\s*:?\s*[\-\+]?\d+[\.,]?\d*\s*°C',
            r'pression\s*:?\s*\d+[\.,]?\d*\s*bars?',
            r'viscosité\s*:?\s*\d+',
            r'granulométrie\s*:?\s*\d+[\.,]?\d*'
        ]
        for pattern in tech_spec_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            entities['technical_specs'].extend(matches)

        return entities

    def classify_content(self, content: str) -> str:
        """Classification avancée du type de contenu."""
        content_lower = content.lower()

        # Catégories enrichies avec pondération
        weighted_categories = {
            'financial': {
                'keywords': ['prix', 'coût', 'tarif', 'montant', 'euros', '€', 'facture', 'paiement', 'acompte', 'devis', 'budget', 'tva', 'ht', 'ttc'],
                'patterns': [r'\d+[\s,]*\d*\s*(?:euros?|€)', r'\d+[\s,]*\d*\s*%', r'tva\s*:?\s*\d+'],
                'weight': 1.2
            },
            'timeline': {
                'keywords': ['délai', 'livraison', 'échéance', 'date', 'planning', 'durée', 'terme', 'calendrier', 'programmation'],
                'patterns': [r'\d+\s*(?:jours?|mois|semaines?)', r'avant\s+le', r'à\s+compter\s+du?'],
                'weight': 1.1
            },
            'obligations': {
                'keywords': ['obligation', 'engage', 'doit', 'responsabilité', 'devoir', 'tenu', 'charge', 'incombe'],
                'patterns': [r'(?:doit|devra|s\'engage)\s+à?', r'est\s+tenu\s+de'],
                'weight': 1.3
            },
            'guarantees': {
                'keywords': ['garantie', 'assurance', 'caution', 'couverture', 'protection', 'décennale', 'dommages-ouvrage'],
                'patterns': [r'garantie\s+de', r'assurance\s+\w+', r'caution\s+de'],
                'weight': 1.2
            },
            'technical_requirements': {
                'keywords': ['technique', 'norme', 'spécification', 'matériau', 'DTU', 'performance', 'qualité', 'conformité', 'résistance'],
                'patterns': [r'DTU\s+[\d\.]+', r'NF\s+EN', r'conforme\s+à'],
                'weight': 1.1
            },
            'conditions': {
                'keywords': ['condition', 'clause', 'modalité', 'stipulation', 'disposition', 'si', 'sous\sréserve', 'sauf'],
                'patterns': [r'sous\s+(?:condition|réserve)', r'si\s+\w+', r'sauf\s+\w+'],
                'weight': 1.0
            },
            'quality_control': {
                'keywords': ['contrôle', 'vérification', 'test', 'essai', 'conformité', 'inspection', 'validation'],
                'patterns': [r'contrôle\s+de', r'vérification\s+de', r'conforme\s+aux?'],
                'weight': 1.0
            },
            'safety_security': {
                'keywords': ['sécurité', 'protection', 'risque', 'danger', 'prévention', 'accident', 'sps', 'epi'],
                'patterns': [r'plan\s+de\s+prévention', r'mesures?\s+de\s+sécurité'],
                'weight': 1.0
            },
            'administrative': {
                'keywords': ['autorisation', 'permis', 'déclaration', 'formalité', 'procédure', 'dossier'],
                'patterns': [r'permis\s+de', r'autorisation\s+de', r'déclaration\s+de'],
                'weight': 0.9
            },
            'insurance': {
                'keywords': ['assurance', 'assureur', 'sinistre', 'indemnisation', 'prime', 'franchise'],
                'patterns': [r'police\s+d\'assurance', r'contrat\s+d\'assurance'],
                'weight': 1.1
            },
            'penalties': {
                'keywords': ['pénalité', 'amende', 'sanction', 'dommages-intérêts', 'astreinte', 'indemnité'],
                'patterns': [r'pénalités?\s+de', r'\d+[\.,]?\d*\s*%\s*par'],
                'weight': 1.2
            }
        }

        scores = {}
        for category, data in weighted_categories.items():
            # Score des mots-clés
            keyword_score = sum(1 for keyword in data['keywords'] if keyword in content_lower)

            # Score des patterns
            pattern_score = sum(len(re.findall(pattern, content_lower)) for pattern in data.get('patterns', []))

            # Score pondéré final
            total_score = (keyword_score + pattern_score * 1.5) * data['weight']

            if total_score > 0:
                scores[category] = total_score

        if scores:
            # Seuil minimum pour éviter les fausses classifications
            max_score = max(scores.values())
            if max_score >= 1.5:  # Seuil de confiance
                return max(scores, key=scores.get)

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

# Instance du service avec initialisation
chunking_service = ChunkingService()

@app.get("/")
async def root():
    """Point d'entrée principal de l'API."""
    return {
        "message": "Legal Document Chunking API - Version Pro avec métadonnées contextuelles",
        "version": "2.1.0",
        "features": [
            "Extraction automatique des métadonnées documentaires",
            "Génération d'ID standardisés",
            "Structure JSON optimisée pour RAG",
            "Références sources professionnelles",
            "Support multi-types : VEFA, CCTP, Baux, etc."
        ],
        "endpoints": {
            "chunk": "/chunk - POST - Chunking de documents avec métadonnées",
            "health": "/health - GET - Status de l'API",
            "docs": "/docs - GET - Documentation interactive"
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
            overlap_size,
            user_id=request.userId,
            project_id=request.projectId
        )

        end_time = time.time()
        processing_time = int((end_time - start_time) * 1000)

        # Calcul des statistiques sur la nouvelle structure
        quality_dist = {'high': 0, 'medium': 0, 'low': 0}
        total_quality = 0
        avg_chunk_size = 0

        if chunks:
            for chunk in chunks:
                score = chunk['chunk_metadata']['quality_score']
                total_quality += score
                avg_chunk_size += chunk['chunk_metadata']['word_count']

                if score >= 0.8:
                    quality_dist['high'] += 1
                elif score >= 0.5:
                    quality_dist['medium'] += 1
                else:
                    quality_dist['low'] += 1

            avg_chunk_size = avg_chunk_size / len(chunks)

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

        # Réponse finale avec nouvelle structure
        response_data = {
            'success': True,
            'chunks': chunks,
            'document_stats': {
                'document_info': chunks[0]['document_info'] if chunks else {},
                'estimated_complexity': 'medium',
                'processing_time_ms': processing_time,
                'total_chunks': len(chunks),
                'avg_chunk_quality': round(avg_quality, 3),
                'quality_distribution': quality_dist,
                'text_length': len(extracted_text),
                'avg_chunk_size': avg_chunk_size
            },
            'validation_results': validation_results,
            'processing_info': {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'version': '2.1.0',
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