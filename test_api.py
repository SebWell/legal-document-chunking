#!/usr/bin/env python3
"""
Test rapide de l'API améliorée
"""

import requests
import json

# Test avec un extrait VEFA réel
test_payload = {
    "extractedText": """CONTRAT DE RESERVATION VEFA
Résidence Urbaine «LE NEST» - Montévrain - Val d'Europe (77)

La Société dénommée SCCV LA VALLEE MONTEVRAIN HOTEL au capital de 20 000 euros,
dont le siège est à BUSSY SAINT GEORGES (77600) - 8, place de la Libération,
immatriculée au RCS de MEAUX sous le numéro 752 123 456, représentée par M. DUPONT
en sa qualité de gérant.

Ci-après dénommée «LE RESERVANT»

Et Ci-après dénommé(s) «LE RESERVATAIRE»

Il est convenu que le réservant s'engage à livrer le logement conforme aux
spécifications techniques du programme «LE NEST» avant le 31 décembre 2013.
Le prix de vente est fixé à 245 000 euros TTC, payable selon l'échéancier suivant.

Article 1 - Objet de la réservation
La présente réservation a pour objet un appartement de type T3 d'une superficie
de 65,50 m² situé au 2ème étage du bâtiment A du programme «LE NEST».

Article 2 - Prix et modalités de paiement
Le prix de vente s'élève à 245 000 euros TTC. Un acompte de 15 000 euros
est exigible à la signature du présent contrat.

Fait à Paris le 15 septembre 2012""",
    "userId": "test-user-quality",
    "projectId": "test-quality-improvement",
    "options": {
        "target_chunk_size": 60,
        "overlap_size": 15
    }
}

print("🧪 Test de l'API améliorée...")
print("="*50)

try:
    # Test local (si l'API tourne)
    response = requests.post("http://localhost:8000/chunk", json=test_payload, timeout=30)

    if response.status_code == 200:
        result = response.json()
        chunks = result.get('chunks', [])

        print(f"✅ API disponible - {len(chunks)} chunks générés")

        # Analyse des scores de qualité
        quality_scores = [chunk['metadata']['quality_score'] for chunk in chunks]
        avg_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        # Distribution de qualité
        high_quality = sum(1 for score in quality_scores if score >= 0.8)
        medium_quality = sum(1 for score in quality_scores if 0.5 <= score < 0.8)
        low_quality = sum(1 for score in quality_scores if score < 0.5)

        print(f"\n📊 Analyse des scores:")
        print(f"  Score moyen: {avg_score:.3f}")
        print(f"  Score min: {min(quality_scores):.3f}")
        print(f"  Score max: {max(quality_scores):.3f}")

        print(f"\n🎯 Distribution qualité:")
        print(f"  HIGH (≥0.8): {high_quality} chunks ({high_quality/len(chunks)*100:.1f}%)")
        print(f"  MEDIUM (0.5-0.8): {medium_quality} chunks ({medium_quality/len(chunks)*100:.1f}%)")
        print(f"  LOW (<0.5): {low_quality} chunks ({low_quality/len(chunks)*100:.1f}%)")

        # Comparaison avec vos résultats précédents
        print(f"\n📈 Comparaison avec résultats précédents:")
        print(f"  AVANT: 0% high quality (score moyen 0.609)")
        print(f"  APRÈS: {high_quality/len(chunks)*100:.1f}% high quality (score moyen {avg_score:.3f})")

        improvement = ((avg_score - 0.609) / 0.609 * 100) if avg_score > 0 else 0
        print(f"  Amélioration score moyen: +{improvement:.1f}%")

        # Exemple de chunk amélioré
        best_chunk = max(chunks, key=lambda x: x['metadata']['quality_score'])
        print(f"\n🏆 Meilleur chunk (score: {best_chunk['metadata']['quality_score']:.3f}):")
        print(f"  Texte: {best_chunk['content']['text'][:100]}...")
        print(f"  Type: {best_chunk['metadata']['content_type']}")
        print(f"  Entités: {len(best_chunk['metadata']['entities']['dates'])} dates, {len(best_chunk['metadata']['entities']['monetary_amounts'])} montants")

    else:
        print(f"❌ Erreur API: {response.status_code}")
        print(response.text)

except requests.exceptions.ConnectionError:
    print("❌ API non disponible sur localhost:8000")
    print("💡 Lancez d'abord: uvicorn main:app --host 0.0.0.0 --port 8000")
except Exception as e:
    print(f"❌ Erreur: {e}")

print(f"\n🎯 Objectif: Atteindre 99% de chunks high-quality")
print("Les améliorations apportées devraient considérablement augmenter les scores!")