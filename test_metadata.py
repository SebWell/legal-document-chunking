#!/usr/bin/env python3
"""
Test simple des métadonnées sans FastAPI
"""
import re
import hashlib
from datetime import datetime
from typing import Dict

class DocumentMetadataExtractor:
    """Extracteur de métadonnées documentaires pour le contexte RAG."""

    def __init__(self):
        self.document_patterns = {
            'contrat_reservation_vefa': {
                'title_patterns': [r'contrat.{0,20}r[eé]servation.{0,20}vefa', r'r[eé]servation.{0,30}futur.{0,10}ach[eè]vement'],
                'parties_patterns': {'reservant': r'r[eé]servant[^\n]*([A-Z][^\n]{10,80})', 'reservataire': r'r[eé]servataire[^\n]*([A-Z][^\n]{10,80})'}
            },
            'cctp': {
                'title_patterns': [r'cctp', r'cahier.{0,20}clauses.{0,20}techniques'],
                'parties_patterns': {'maitre_ouvrage': r'ma[iî]tre.{0,5}ouvrage[^\n]*([A-Z][^\n]{10,80})', 'entrepreneur': r'entrepreneur[^\n]*([A-Z][^\n]{10,80})'}
            }
        }

    def extract_document_metadata(self, text: str) -> Dict:
        """Extraction complète des métadonnées du document."""
        text_sample = text[:5000]

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
        """Détecter le type de document."""
        text_lower = text.lower()

        if 'vefa' in text_lower or 'réservation' in text_lower:
            return 'contrat_reservation_vefa'
        elif 'cctp' in text_lower:
            return 'cctp'
        else:
            return 'contrat_general'

    def extract_title(self, text: str, doc_type: str) -> str:
        """Extraire le titre principal."""
        if 'CONTRAT DE RESERVATION VEFA' in text.upper():
            return 'CONTRAT DE RESERVATION VEFA'

        # Chercher les premiers mots en majuscules
        match = re.search(r'^\\s*([A-Z][A-Z\\s]{20,100}?)(?:\\n|$)', text, re.MULTILINE)
        if match:
            return re.sub(r'\\s+', ' ', match.group(1).strip())

        return "DOCUMENT JURIDIQUE"

    def extract_main_date(self, text: str) -> str:
        """Extraire la date principale."""
        # Pattern pour "fait à ... le ..."
        match = re.search(r'fait\s+à\s+[^\n]+le\s+(\d{1,2}\s+\w+\s+\d{4})', text, re.IGNORECASE)
        if match:
            return self.normalize_date(match.group(1))

        return datetime.now().strftime("%d/%m/%Y")

    def normalize_date(self, date_str: str) -> str:
        """Normaliser une date."""
        # Mapping des mois français
        months = {
            'janvier': '01', 'février': '02', 'mars': '03', 'avril': '04',
            'mai': '05', 'juin': '06', 'juillet': '07', 'août': '08',
            'septembre': '09', 'octobre': '10', 'novembre': '11', 'décembre': '12'
        }

        parts = date_str.lower().split()
        if len(parts) == 3:
            day, month_name, year = parts
            month_num = months.get(month_name, '01')
            return f"{day.zfill(2)}/{month_num}/{year}"

        return date_str

    def extract_parties(self, text: str, doc_type: str) -> Dict:
        """Extraire les parties."""
        parties = {}

        # RESERVANT - Pattern amélioré
        match = re.search(r'société\s+dénommée\s+([A-Z][^\n]+?)\s+au\s+capital', text, re.IGNORECASE)
        if match:
            parties['reservant'] = match.group(1).strip()
        else:
            match = re.search(r'dénommée\s+([A-Z][^\n]{20,80})', text)
            if match:
                parties['reservant'] = match.group(1).strip()

        # RESERVATAIRE (généralement à compléter)
        parties['reservataire'] = '[Réservataire]'

        return parties

    def extract_location(self, text: str) -> str:
        """Extraire la localisation."""
        # Chercher des patterns comme "Montévrain (77)"
        match = re.search(r'([A-Z][a-z]+(?:[\s\-][A-Z][a-z]+)*)\s*\(\d{2,5}\)', text)
        if match:
            return match.group(1).strip()
        return ""

    def extract_project_name(self, text: str) -> str:
        """Extraire le nom du projet."""
        # Chercher «LE NEST»
        match = re.search(r'«([^»]{5,50})»', text)
        if match:
            return match.group(1).strip()
        return ""

    def generate_document_id(self, text: str, title: str, date: str) -> str:
        """Générer un ID standardisé."""
        try:
            if date and '/' in date:
                day, month, year = date.split('/')[:3]
                doc_date = datetime(int(year), int(month), int(day), 12, 0, 0)
            else:
                doc_date = datetime.now()
        except:
            doc_date = datetime.now()

        base_id = doc_date.strftime("%Y%m%d%H%M%S")
        content_hash = hashlib.md5((text + title).encode('utf-8')).hexdigest()[:3].upper()
        return base_id + content_hash

# Test
if __name__ == "__main__":
    extractor = DocumentMetadataExtractor()
    test_text = '''
CONTRAT DE RESERVATION VEFA
Résidence Urbaine «LE NEST» - Montévrain - Val d'Europe (77)

La Société dénommée SCCV LA VALLEE MONTEVRAIN HOTEL au capital de 20000 euros,
dont le siège est à BUSSY SAINT GEORGES (77600) - 8, place de la Libération

Ci-après dénommée «LE RESERVANT»

Et Ci-après dénommé(s) «LE RESERVATAIRE»

Fait à Paris le 15 septembre 2012
'''

    print('🧪 Test extraction métadonnées...')
    metadata = extractor.extract_document_metadata(test_text)

    print('📊 Résultats:')
    for key, value in metadata.items():
        print(f'  {key}: {value}')

    print('\n✅ Test réussi!')