"""
🤖 DATA COLLECT - Orchestrateur Principal
==========================================
Coordonne tous les robots de collecte de données

UTILISATION:
-----------
python data_collect.py --query "BRCA1 breast cancer" --all
python data_collect.py --query "TP53 p53 cancer" --papers --sequences
python data_collect.py --query "Alzheimer tau protein" --max 50

ROBOTS DISPONIBLES:
------------------
- papers: Articles PubMed (ArticleDocument)
- images: Pathways KEGG (ImageDocument)
- experiments: Datasets GEO (ExperimentDocument)
- sequences: Protéines UniProt (ProteinDocument)
- structures: Structures 3D PDB (StructureDocument)
"""

import argparse
import os
import json
from datetime import datetime
from typing import List

from robots import (
    RobotPapers,
    RobotImages,
    RobotExperiments,
    RobotSequences,
    RobotStructures
)


# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


def setup_directories():
    """Crée la structure de dossiers"""
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"📁 Dossier de données: {DATA_DIR}")


def extract_genes_and_keywords(query: str) -> tuple:
    """
    Extrait les gènes et mots-clés d'une requête
    
    Returns:
        (genes, keywords, organism)
    """
    import re
    
    # Gènes communs
    common_genes = {
        "BRCA1", "BRCA2", "TP53", "P53", "KRAS", "EGFR", 
        "BRAF", "PTEN", "AKT1", "MYC", "BCL2", "VEGF",
        "APP", "MAPT", "TAU", "SNCA", "HTT"
    }
    
    # Mots-clés maladies
    disease_keywords = {
        "cancer", "tumor", "carcinoma", "leukemia", "lymphoma",
        "alzheimer", "parkinson", "diabetes", "disease",
        "breast", "lung", "prostate", "colon", "ovarian"
    }
    
    # Organisme
    organism = "Homo sapiens"  # défaut
    if "mouse" in query.lower():
        organism = "Mus musculus"
    elif "rat" in query.lower():
        organism = "Rattus norvegicus"
    
    # Extraire gènes
    query_upper = query.upper()
    genes = [g for g in common_genes if g in query_upper]
    
    # Extraire keywords
    query_lower = query.lower()
    keywords = [kw for kw in disease_keywords if kw in query_lower]
    
    return genes, keywords, organism


# ============================================================================
# ORCHESTRATEUR PRINCIPAL
# ============================================================================

class DataCollector:
    """
    Orchestrateur principal qui coordonne tous les robots
    """
    
    def __init__(self):
        setup_directories()
        
        # Initialiser tous les robots
        self.robot_papers = RobotPapers(DATA_DIR)
        self.robot_images = RobotImages(DATA_DIR)
        self.robot_experiments = RobotExperiments(DATA_DIR)
        self.robot_sequences = RobotSequences(DATA_DIR)
        self.robot_structures = RobotStructures(DATA_DIR)
        
        print("\n" + "="*70)
        print("🤖 DATA COLLECTOR - Système de collecte automatique")
        print("="*70)
    
    
    def collect_all(self, query: str, max_results: int = 100):
        """
        Collecte depuis TOUTES les sources
        
        Args:
            query: Requête de recherche (ex: "BRCA1 breast cancer")
            max_results: Nombre maximum de résultats par source
        """
        print(f"\n📋 Requête: {query}")
        print(f"🎯 Max résultats: {max_results}")
        
        # Extraire contexte
        genes, keywords, organism = extract_genes_and_keywords(query)
        print(f"\n🧬 Gènes détectés: {genes}")
        print(f"🔑 Mots-clés: {keywords}")
        print(f"🦠 Organisme: {organism}")
        
        # Si pas de gènes, utiliser des defaults
        if not genes:
            print("⚠️ Aucun gène détecté - utilisation de gènes par défaut")
            if "cancer" in keywords:
                genes = ["TP53", "KRAS", "BRCA1"]
            elif "alzheimer" in keywords:
                genes = ["APP", "MAPT"]
            else:
                genes = ["TP53"]
        
        # Stats globales
        stats = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "results": {}
        }
        
        # 1. ARTICLES
        print(f"\n{'='*70}")
        print("1️⃣ COLLECTE D'ARTICLES")
        print("="*70)
        n_papers = self.robot_papers.collect(query, max_results)
        stats["results"]["papers"] = n_papers
        
        # 2. IMAGES (Pathways)
        print(f"\n{'='*70}")
        print("2️⃣ COLLECTE D'IMAGES")
        print("="*70)
        n_images = self.robot_images.collect()
        stats["results"]["images"] = n_images
        
        # 3. EXPERIMENTS
        print(f"\n{'='*70}")
        print("3️⃣ COLLECTE D'EXPÉRIENCES")
        print("="*70)
        
        # Utiliser gènes détectés ou defaults
        if not genes:
            genes = ["TP53"]
        
        n_experiments = self.robot_experiments.collect(
            genes=genes,
            keywords=keywords,
            organism=organism,
            max_per_gene=5  # 5 datasets par gène
        )
        stats["results"]["experiments"] = n_experiments
        
        # 4. SEQUENCES
        print(f"\n{'='*70}")
        print("4️⃣ COLLECTE DE SÉQUENCES")
        print("="*70)
        n_sequences = self.robot_sequences.collect(
            query=query,
            organism=organism.split()[0].lower(),
            max_results=max_results // 2
        )
        stats["results"]["sequences"] = n_sequences
        
        # 5. STRUCTURES PDB
        print(f"\n{'='*70}")
        print("5️⃣ COLLECTE DE STRUCTURES PDB")
        print("="*70)
        n_structures = self.robot_structures.collect(
            query=query,
            max_results=max_results // 3
        )
        stats["results"]["structures"] = n_structures
        
        # 6. ALPHAFOLD
        print(f"\n{'='*70}")
        print("6️⃣ COLLECTE ALPHAFOLD")
        print("="*70)
        n_alphafold = self.robot_structures.collect_alphafold_from_proteins(max_results)
        stats["results"]["structures-alphafold"] = n_alphafold
        
        # Résumé final
        self._print_summary(stats)
        
        # Sauvegarder les stats
        self._save_stats(stats)
    
    
    def collect_specific(self, query: str, robots: List[str], max_results: int = 100):
        """
        Collecte depuis des robots spécifiques
        
        Args:
            query: Requête de recherche
            robots: Liste des robots à utiliser ['papers', 'sequences', etc.]
            max_results: Nombre maximum de résultats
        """
        print(f"\n📋 Requête: {query}")
        print(f"🎯 Robots: {', '.join(robots)}")
        print(f"🎯 Max résultats: {max_results}")
        
        # Extraire contexte
        genes, keywords, organism = extract_genes_and_keywords(query)
        
        stats = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "robots": robots,
            "results": {}
        }
        
        # Exécuter les robots demandés
        if "papers" in robots:
            print(f"\n{'='*70}")
            print("📄 COLLECTE D'ARTICLES")
            print("="*70)
            n = self.robot_papers.collect(query, max_results)
            stats["results"]["papers"] = n
        
        if "images" in robots:
            print(f"\n{'='*70}")
            print("🖼️ COLLECTE D'IMAGES")
            print("="*70)
            n = self.robot_images.collect()
            stats["results"]["images"] = n
        
        if "experiments" in robots:
            print(f"\n{'='*70}")
            print("🧪 COLLECTE D'EXPÉRIENCES")
            print("="*70)
            if not genes:
                genes = ["TP53"]  # Gène par défaut
            n = self.robot_experiments.collect(genes, keywords, organism, max_per_gene=5)
            stats["results"]["experiments"] = n
        
        if "sequences" in robots:
            print(f"\n{'='*70}")
            print("🧬 COLLECTE DE SÉQUENCES")
            print("="*70)
            n = self.robot_sequences.collect(query, organism.split()[0].lower(), max_results // 2)
            stats["results"]["sequences"] = n
        
        if "structures" in robots:
            print(f"\n{'='*70}")
            print("🔬 COLLECTE DE STRUCTURES PDB")
            print("="*70)
            n = self.robot_structures.collect(query, max_results // 3)
            stats["results"]["structures"] = n
        
        if "structures-alphafold" in robots:
            print(f"\n{'='*70}")
            print("🤖 COLLECTE ALPHAFOLD")
            print("="*70)
            n = self.robot_structures.collect_alphafold_from_proteins(max_results)
            stats["results"]["structures-alphafold"] = n
        
        # Résumé
        self._print_summary(stats)
        self._save_stats(stats)
    
    
    def _print_summary(self, stats: dict):
        """Affiche le résumé de la collecte"""
        print(f"\n{'='*70}")
        print("📊 RÉSUMÉ DE LA COLLECTE")
        print("="*70)
        print(f"\n🔍 Requête: {stats['query']}")
        print(f"⏰ Date: {stats['timestamp']}")
        print(f"\n📈 Résultats:")
        
        total = 0
        for source, count in stats["results"].items():
            print(f"   • {source:15}: {count:4} nouveaux")
            total += count
        
        print(f"\n✅ Total: {total} nouvelles entrées")
        print("="*70)
    
    
    def _save_stats(self, stats: dict):
        """Sauvegarde les statistiques de collecte"""
        stats_file = os.path.join(DATA_DIR, "collection_stats.json")
        
        # Charger stats existantes
        all_stats = []
        if os.path.exists(stats_file):
            with open(stats_file, 'r', encoding='utf-8') as f:
                all_stats = json.load(f)
        
        # Ajouter nouvelles stats
        all_stats.append(stats)
        
        # Sauvegarder
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(all_stats, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Statistiques sauvegardées: {stats_file}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="🤖 Data Collector - Système de collecte automatique",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python data_collect.py --query "BRCA1 breast cancer" --all
  python data_collect.py --query "TP53 p53 cancer" --papers --sequences
  python data_collect.py --query "Alzheimer tau protein" --experiments --max 50
        """
    )
    
    # Arguments
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Requête de recherche (ex: 'BRCA1 breast cancer')"
    )
    
    parser.add_argument(
        "--max",
        type=int,
        default=100,
        help="Nombre maximum de résultats par source (défaut: 100)"
    )
    
    # Robots
    parser.add_argument("--all", action="store_true", help="Utiliser tous les robots")
    parser.add_argument("--papers", action="store_true", help="Collecter des articles")
    parser.add_argument("--images", action="store_true", help="Collecter des images")
    parser.add_argument("--experiments", action="store_true", help="Collecter des expériences")
    parser.add_argument("--sequences", action="store_true", help="Collecter des séquences")
    parser.add_argument("--structures", action="store_true", help="Collecter des structures PDB")
    parser.add_argument("--structures-alphafold", action="store_true", help="Collecter AlphaFold depuis proteins.json")
    
    args = parser.parse_args()
    
    # Créer le collecteur
    collector = DataCollector()
    
    # Déterminer les robots à utiliser
    if args.all:
        collector.collect_all(args.query, args.max)
    else:
        robots = []
        if args.papers:
            robots.append("papers")
        if args.images:
            robots.append("images")
        if args.experiments:
            robots.append("experiments")
        if args.sequences:
            robots.append("sequences")
        if args.structures:
            robots.append("structures")
        if args.structures_alphafold:
            robots.append("structures-alphafold")
        
        if not robots:
            print("❌ Aucun robot sélectionné. Utilisez --all ou spécifiez des robots.")
            print("   Exemple: python data_collect.py --query 'cancer' --papers --sequences")
            return
        
        collector.collect_specific(args.query, robots, args.max)


if __name__ == "__main__":
    main()
