"""
🧹 DATA PREPROCESSING - Nettoyage et validation des données
============================================================
Élimine les entrées avec champs vides importants
Valide la structure des documents avant indexation

UTILISATION:
-----------
python preprocess_data.py --all
python preprocess_data.py --proteins --articles
python preprocess_data.py --validate-only
"""

import argparse
import json
import os
from typing import List, Dict, Any, Tuple
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Champs obligatoires par type de document
REQUIRED_FIELDS = {
    "proteins": ["uniprot_id", "protein_name", "sequence"],
    "articles": ["title", "abstract"],  # pmid optionnel
    "images": ["caption", "source"],  # file_path ou url requis
    "experiments": ["accession", "title"],
    "structures": ["title"],  # pdb_id ou alphafold_id requis
}

# Champs recommandés (warning si manquants)
RECOMMENDED_FIELDS = {
    "proteins": ["gene_names", "function", "normalized_bridge"],
    "articles": ["pmid", "doi", "authors", "normalized_bridge"],
    "images": ["description", "normalized_bridge"],
    "experiments": ["summary", "organism", "normalized_bridge"],
    "structures": ["method", "resolution", "normalized_bridge"],
}


# ============================================================================
# FONCTIONS DE VALIDATION
# ============================================================================


def validate_protein(doc: dict) -> Tuple[bool, List[str]]:
    """Valide un ProteinDocument"""
    errors = []

    # Champs obligatoires
    if not doc.get("uniprot_id"):
        errors.append("uniprot_id manquant")
    if not doc.get("protein_name"):
        errors.append("protein_name manquant")
    if not doc.get("sequence") or len(doc.get("sequence", "")) < 10:
        errors.append("sequence manquante ou trop courte (<10 aa)")

    return len(errors) == 0, errors


def validate_article(doc: dict) -> Tuple[bool, List[str]]:
    """Valide un ArticleDocument"""
    errors = []

    if not doc.get("title") or len(doc.get("title", "")) < 5:
        errors.append("title manquant ou trop court")
    if not doc.get("abstract") or len(doc.get("abstract", "")) < 50:
        errors.append("abstract manquant ou trop court (<50 chars)")

    return len(errors) == 0, errors


def validate_image(doc: dict) -> Tuple[bool, List[str]]:
    """Valide un ImageDocument"""
    errors = []

    if not doc.get("caption"):
        errors.append("caption manquant")
    if not doc.get("source"):
        errors.append("source manquant")

    # Doit avoir file_path OU url
    if not doc.get("file_path") and not doc.get("url"):
        errors.append("file_path ou url requis")

    return len(errors) == 0, errors


def validate_experiment(doc: dict) -> Tuple[bool, List[str]]:
    """Valide un ExperimentDocument"""
    errors = []

    if not doc.get("accession"):
        errors.append("accession manquant")
    if not doc.get("title"):
        errors.append("title manquant")

    return len(errors) == 0, errors


def validate_structure(doc: dict) -> Tuple[bool, List[str]]:
    """Valide un StructureDocument"""
    errors = []

    if not doc.get("title"):
        errors.append("title manquant")

    # Doit avoir pdb_id OU alphafold_id
    if not doc.get("pdb_id") and not doc.get("alphafold_id"):
        errors.append("pdb_id ou alphafold_id requis")

    # Doit avoir file_path
    if not doc.get("file_path"):
        errors.append("file_path manquant (fichier PDB)")

    return len(errors) == 0, errors


VALIDATORS = {
    "proteins": validate_protein,
    "articles": validate_article,
    "images": validate_image,
    "experiments": validate_experiment,
    "structures": validate_structure,
}


# ============================================================================
# FONCTIONS D'ENRICHISSEMENT
# ============================================================================


def enrich_normalized_bridge(doc: dict, doc_type: str) -> dict:
    """Ajoute un normalized_bridge vide si manquant"""
    if "normalized_bridge" not in doc or doc["normalized_bridge"] is None:
        doc["normalized_bridge"] = {
            "genes": [],
            "diseases": [],
            "processes": [],
            "pathways": [],
            "keywords": [],
        }
    else:
        # S'assurer que tous les champs existent
        bridge = doc["normalized_bridge"]
        for field in ["genes", "diseases", "processes", "pathways", "keywords"]:
            if field not in bridge or bridge[field] is None:
                bridge[field] = []

    return doc


def enrich_protein(doc: dict) -> dict:
    """Enrichit un ProteinDocument"""
    doc = enrich_normalized_bridge(doc, "proteins")

    # Ajouter gene_names au bridge si présent
    if doc.get("gene_names") and doc["normalized_bridge"]:
        existing_genes = set(doc["normalized_bridge"].get("genes", []))
        for gene in doc["gene_names"]:
            existing_genes.add(gene.upper())
        doc["normalized_bridge"]["genes"] = list(existing_genes)

    return doc


def enrich_article(doc: dict) -> dict:
    """Enrichit un ArticleDocument"""
    doc = enrich_normalized_bridge(doc, "articles")
    return doc


def enrich_image(doc: dict) -> dict:
    """Enrichit un ImageDocument"""
    doc = enrich_normalized_bridge(doc, "images")

    # Ajouter description si manquante (utiliser caption)
    if not doc.get("description") and doc.get("caption"):
        doc["description"] = doc["caption"]

    return doc


def enrich_experiment(doc: dict) -> dict:
    """Enrichit un ExperimentDocument"""
    doc = enrich_normalized_bridge(doc, "experiments")

    # Ajouter measurements vides si manquants
    if "measurements" not in doc or doc["measurements"] is None:
        doc["measurements"] = []

    return doc


def enrich_structure(doc: dict) -> dict:
    """Enrichit un StructureDocument"""
    doc = enrich_normalized_bridge(doc, "structures")
    return doc


ENRICHERS = {
    "proteins": enrich_protein,
    "articles": enrich_article,
    "images": enrich_image,
    "experiments": enrich_experiment,
    "structures": enrich_structure,
}


# ============================================================================
# PRÉTRAITEMENT PRINCIPAL
# ============================================================================


class DataPreprocessor:
    """Préprocesseur de données"""

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.stats = {
            "processed": 0,
            "valid": 0,
            "invalid": 0,
            "enriched": 0,
            "removed": 0,
        }

    def process_collection(self, collection: str, validate_only: bool = False) -> dict:
        """
        Traite une collection

        Args:
            collection: Nom de la collection (proteins, articles, etc.)
            validate_only: Si True, ne modifie pas les fichiers

        Returns:
            Statistiques de traitement
        """
        filepath = os.path.join(self.data_dir, f"{collection}.json")

        if not os.path.exists(filepath):
            print(f"⚠️  Fichier non trouvé: {filepath}")
            return {"error": "file_not_found"}

        print(f"\n{'='*60}")
        print(f"📁 Traitement: {collection}")
        print(f"{'='*60}")

        # Charger données
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        print(f"   📊 Documents chargés: {len(data)}")

        validator = VALIDATORS.get(collection)
        enricher = ENRICHERS.get(collection)

        valid_docs = []
        invalid_docs = []

        for i, doc in enumerate(data):
            # Valider
            is_valid, errors = validator(doc)

            if is_valid:
                # Enrichir
                if enricher and not validate_only:
                    doc = enricher(doc)
                valid_docs.append(doc)
            else:
                invalid_docs.append({"index": i, "doc": doc, "errors": errors})
                print(f"   ❌ [{i}] Invalide: {', '.join(errors)}")

        # Stats
        stats = {
            "total": len(data),
            "valid": len(valid_docs),
            "invalid": len(invalid_docs),
            "removed": len(invalid_docs),
        }

        print(f"\n   ✅ Valides: {stats['valid']}")
        print(f"   ❌ Invalides: {stats['invalid']}")

        # Sauvegarder si pas validate_only
        if not validate_only and len(valid_docs) > 0:
            # Backup
            backup_path = filepath.replace(
                ".json", f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"   💾 Backup: {backup_path}")

            # Sauvegarder données nettoyées
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(valid_docs, f, indent=2, ensure_ascii=False)
            print(f"   💾 Sauvegardé: {filepath} ({len(valid_docs)} documents)")

        # Sauvegarder documents invalides pour review
        if invalid_docs:
            invalid_path = os.path.join(self.data_dir, f"{collection}_invalid.json")
            with open(invalid_path, "w", encoding="utf-8") as f:
                json.dump(invalid_docs, f, indent=2, ensure_ascii=False)
            print(f"   📝 Invalides sauvegardés: {invalid_path}")

        return stats

    def process_all(self, validate_only: bool = False) -> dict:
        """Traite toutes les collections"""
        collections = ["proteins", "articles", "images", "experiments", "structures"]

        all_stats = {}
        for collection in collections:
            stats = self.process_collection(collection, validate_only)
            all_stats[collection] = stats

        # Résumé
        print(f"\n{'='*60}")
        print("📊 RÉSUMÉ DU PRÉTRAITEMENT")
        print(f"{'='*60}")

        total_valid = 0
        total_invalid = 0

        for coll, stats in all_stats.items():
            if "error" not in stats:
                print(
                    f"   {coll:12}: {stats['valid']:4} valides / {stats['invalid']:4} invalides"
                )
                total_valid += stats["valid"]
                total_invalid += stats["invalid"]

        print(f"\n   TOTAL: {total_valid} valides / {total_invalid} invalides")

        return all_stats


# ============================================================================
# MAIN
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="🧹 Data Preprocessing - Nettoyage et validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--all", action="store_true", help="Traiter toutes les collections"
    )
    parser.add_argument("--proteins", action="store_true", help="Traiter proteins.json")
    parser.add_argument("--articles", action="store_true", help="Traiter articles.json")
    parser.add_argument("--images", action="store_true", help="Traiter images.json")
    parser.add_argument(
        "--experiments", action="store_true", help="Traiter experiments.json"
    )
    parser.add_argument(
        "--structures", action="store_true", help="Traiter structures.json"
    )
    parser.add_argument(
        "--validate-only", action="store_true", help="Valider sans modifier"
    )

    args = parser.parse_args()

    preprocessor = DataPreprocessor()

    if args.all:
        preprocessor.process_all(args.validate_only)
    else:
        collections = []
        if args.proteins:
            collections.append("proteins")
        if args.articles:
            collections.append("articles")
        if args.images:
            collections.append("images")
        if args.experiments:
            collections.append("experiments")
        if args.structures:
            collections.append("structures")

        if not collections:
            print(
                "❌ Aucune collection spécifiée. Utilisez --all ou --proteins, --articles, etc."
            )
            return

        for coll in collections:
            preprocessor.process_collection(coll, args.validate_only)


if __name__ == "__main__":
    main()
