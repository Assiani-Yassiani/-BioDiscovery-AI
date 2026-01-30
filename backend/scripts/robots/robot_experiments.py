"""
🧪 ROBOT EXPERIMENTS - Collecte de données GEO
==============================================
Adapté au schéma ExperimentDocument
Génère des measurements simulées pour les démonstrations

SOURCE: NCBI GEO (Gene Expression Omnibus)
URL: https://www.ncbi.nlm.nih.gov/geo/
"""

import requests
import json
import time
import os
import re
import random
from datetime import datetime
from typing import List, Dict, Optional

from app.models.schemas import ExperimentDocument, NormalizedBridge


# ============================================================================
# EXTRACTION GÈNES DEPUIS TEXTE
# ============================================================================


def extract_genes_from_text(text: str) -> List[str]:
    """Extraction NLP basique de noms de gènes"""
    if not text:
        return []

    # Patterns communs de gènes
    gene_patterns = [
        r"\b([A-Z][A-Z0-9]{1,9})\b",  # BRCA1, TP53, IL17F
        r"\b(p\d+)\b",  # p53
    ]

    genes = set()
    for pattern in gene_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        genes.update(matches)

    # Filtre: gènes connus seulement
    known_genes = {
        "BRCA1",
        "BRCA2",
        "TP53",
        "KRAS",
        "EGFR",
        "APP",
        "MAPT",
        "TAU",
        "IL17F",
        "IFNG",
        "TNF",
        "IL6",
        "PTEN",
        "AKT1",
        "BRAF",
        "MYC",
        "BCL2",
        "BAX",
        "CDK4",
        "RB1",
        "ERBB2",
        "APC",
        "PIK3CA",
        "ALK",
        "P53",
        "ERK",
        "SNCA",
        "PARK2",
        "PSEN1",
        "SOD1",
        "HTT",
    }

    return [g.upper() for g in genes if g.upper() in known_genes]


# ============================================================================
# ROBOT EXPERIMENTS GEO
# ============================================================================


class RobotExperiments:
    """
    Collecte de datasets GEO (Gene Expression Omnibus)
    Output: ExperimentDocument avec measurements simulées

    GEO contient des données d'expression génique provenant de:
    - Microarrays (Affymetrix, Agilent, etc.)
    - RNA-seq
    - ChIP-seq
    - Et autres technologies high-throughput
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        self.base_url = "https://www.ncbi.nlm.nih.gov/geo"
        self.api_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

        self.experiments = self._load_existing()

    def _load_existing(self) -> Dict[str, ExperimentDocument]:
        """Charge les expériences existantes"""
        filepath = os.path.join(self.output_dir, "experiments.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {exp["accession"]: ExperimentDocument(**exp) for exp in data}
        return {}

    def _save(self):
        """Sauvegarde les expériences"""
        filepath = os.path.join(self.output_dir, "experiments.json")
        experiments = [exp.model_dump() for exp in self.experiments.values()]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(experiments, f, indent=2, ensure_ascii=False)

    def _generate_measurements(
        self, gene: str, n_samples: int, experiment_type: str = "expression"
    ) -> List[dict]:
        """
        Génère des measurements simulées pour démonstration

        Dans un cas réel, ces données proviendraient du parsing des fichiers:
        - SOFT format (Series Matrix)
        - MINiML format (XML)
        - Supplementary files (processed data)

        Args:
            gene: Nom du gène étudié
            n_samples: Nombre d'échantillons dans le dataset
            experiment_type: Type d'expérience (expression, methylation, etc.)

        Returns:
            Liste de measurements avec conditions et valeurs
        """
        measurements = []

        # Conditions typiques dans les études GEO
        condition_sets = {
            "cancer": ["normal", "tumor", "metastasis"],
            "treatment": ["control", "treated_24h", "treated_48h", "treated_72h"],
            "disease": ["healthy", "disease_early", "disease_late"],
            "knockout": ["wildtype", "heterozygous", "knockout"],
            "timecourse": ["0h", "6h", "12h", "24h", "48h"],
        }

        # Choisir un set de conditions aléatoire
        condition_type = random.choice(list(condition_sets.keys()))
        conditions = condition_sets[condition_type]

        # Générer measurements pour chaque sample
        actual_samples = min(n_samples, 20)  # Max 20 samples

        for i in range(actual_samples):
            condition = conditions[i % len(conditions)]

            # Générer valeur d'expression basée sur la condition
            if condition in ["normal", "healthy", "wildtype", "control", "0h"]:
                # Baseline expression
                base_value = 1.0
                fold_change = 1.0
            elif condition in ["tumor", "disease_late", "knockout", "treated_72h"]:
                # Strong effect
                base_value = (
                    random.uniform(2.0, 5.0)
                    if random.random() > 0.3
                    else random.uniform(0.1, 0.5)
                )
                fold_change = base_value
            else:
                # Moderate effect
                base_value = random.uniform(0.5, 2.5)
                fold_change = base_value

            # Ajouter du bruit
            expression_value = base_value * random.uniform(0.8, 1.2)
            fold_change = fold_change * random.uniform(0.9, 1.1)

            # Déterminer le label
            if fold_change > 1.5:
                label = "upregulated"
            elif fold_change < 0.67:
                label = "downregulated"
            else:
                label = "unchanged"

            # P-value simulée (plus significative pour les gros changements)
            if abs(fold_change - 1.0) > 1.0:
                p_value = random.uniform(0.0001, 0.01)
            elif abs(fold_change - 1.0) > 0.5:
                p_value = random.uniform(0.01, 0.05)
            else:
                p_value = random.uniform(0.05, 0.5)

            measurement = {
                "sample_id": f"GSM{random.randint(1000000, 9999999)}",
                "condition": condition,
                "replicate": (i // len(conditions)) + 1,
                "gene": gene,
                "expression_value": round(expression_value, 3),
                "fold_change": round(fold_change, 3),
                "p_value": round(p_value, 6),
                "label": label,
            }

            measurements.append(measurement)

        return measurements

    def _extract_conditions_from_summary(self, summary: str) -> List[str]:
        """Extrait les conditions expérimentales du résumé"""
        conditions = set()

        # Patterns de conditions
        patterns = {
            "treatment": ["treated", "treatment", "drug", "compound"],
            "disease": ["patient", "disease", "cancer", "tumor"],
            "knockout": ["knockout", "knockdown", "siRNA", "shRNA"],
            "timecourse": ["time course", "time point", "hours", "days"],
        }

        summary_lower = summary.lower()

        for condition_type, keywords in patterns.items():
            if any(kw in summary_lower for kw in keywords):
                conditions.add(condition_type)

        return list(conditions) if conditions else ["unspecified"]

    def search_geo(
        self,
        gene: str,
        keywords: List[str] = None,
        organism: str = "Homo sapiens",
        max_results: int = 10,
    ) -> List[str]:
        """Recherche des datasets GEO"""
        print(f"\n🔍 Recherche GEO: {gene} + {keywords}")

        try:
            # Mapper organism
            organism_map = {
                "Homo sapiens": "human",
                "Mus musculus": "mouse",
                "Rattus norvegicus": "rat",
            }
            organism_term = organism_map.get(organism, organism)

            # Construire query
            query_parts = [f"{gene}[Gene Symbol]"]
            if keywords:
                query_parts.extend([f"{kw}[All Fields]" for kw in keywords[:2]])
            query_parts.append(f"{organism_term}[Organism]")

            # ESearch pour trouver GSE IDs
            url = f"{self.api_url}/esearch.fcgi"
            params = {
                "db": "gds",
                "term": " AND ".join(query_parts),
                "retmax": max_results,
                "retmode": "json",
            }

            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                print(f"   ✅ {len(ids)} datasets trouvés ({organism})")
                return ids
        except Exception as e:
            print(f"   ❌ Erreur: {e}")

        return []

    def get_details(self, gds_id: str, gene: str) -> Optional[dict]:
        """Obtient les détails d'un dataset GEO"""
        try:
            # ESummary pour obtenir métadonnées
            url = f"{self.api_url}/esummary.fcgi"
            params = {"db": "gds", "id": gds_id, "retmode": "json"}

            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {}).get(gds_id, {})

                # Extraire infos
                accession = result.get("accession", "")
                title = result.get("title", "")
                summary = result.get("summary", "")
                organism = result.get("taxon", "")
                samples = result.get("n_samples", 0)
                gpl = result.get("gpl", "")  # Platform
                gse_type = result.get("gdstype", "")  # Type de dataset

                return {
                    "gse_accession": accession,
                    "title": title,
                    "summary": summary,
                    "organism": organism,
                    "n_samples": (
                        samples
                        if isinstance(samples, int)
                        else int(samples) if samples else 10
                    ),
                    "platform": gpl,
                    "gds_type": gse_type,
                    "gene": gene,
                }
        except Exception as e:
            print(f"   ⚠️ Détails {gds_id}: {e}")

        return None

    def collect(
        self,
        genes: List[str],
        keywords: List[str] = None,
        organism: str = "Homo sapiens",
        max_per_gene: int = 5,
    ) -> int:
        """
        Collecte des datasets GEO avec measurements générées

        Args:
            genes: Liste de gènes à rechercher
            keywords: Mots-clés de contexte (cancer, disease, etc.)
            organism: Organisme cible
            max_per_gene: Nombre max de datasets par gène

        Returns:
            Nombre de nouveaux experiments collectés
        """
        print(f"\n{'='*60}")
        print(f"🧪 ROBOT EXPERIMENTS - GEO")
        print(f"   Gènes: {genes}")
        print(f"   Organisme: {organism}")
        print(f"   Mots-clés: {keywords}")
        print(f"{'='*60}")

        if keywords is None:
            keywords = []

        collected = 0

        for gene in genes:
            # Rechercher datasets
            gds_ids = self.search_geo(gene, keywords, organism, max_per_gene)

            for gds_id in gds_ids:
                details = self.get_details(gds_id, gene)

                if details and details["gse_accession"]:
                    accession = details["gse_accession"]

                    # Skip si déjà existant
                    if accession in self.experiments:
                        print(f"   ⏭️  {accession} déjà collecté")
                        continue

                    # Extraire conditions du résumé
                    conditions = self._extract_conditions_from_summary(
                        details["summary"]
                    )

                    # Générer measurements simulées
                    n_samples = details["n_samples"]
                    measurements = self._generate_measurements(
                        gene=gene,
                        n_samples=n_samples,
                        experiment_type=details.get("gds_type", "expression"),
                    )

                    # Créer NormalizedBridge
                    # Extraire gènes additionnels du résumé
                    additional_genes = extract_genes_from_text(details["summary"])
                    all_genes = list(set([gene.upper()] + additional_genes))

                    normalized_bridge = NormalizedBridge(
                        genes=all_genes,
                        diseases=[
                            kw
                            for kw in keywords
                            if kw
                            in ["cancer", "tumor", "disease", "alzheimer", "parkinson"]
                        ],
                        keywords=keywords + conditions,
                    )

                    # Déterminer le type de données
                    data_type = "expression"
                    if "methylation" in details["summary"].lower():
                        data_type = "methylation"
                    elif "chip" in details["summary"].lower():
                        data_type = "chip-seq"
                    elif (
                        "rna-seq" in details["summary"].lower()
                        or "rnaseq" in details["summary"].lower()
                    ):
                        data_type = "rna-seq"

                    # Créer ExperimentDocument
                    exp_doc = ExperimentDocument(
                        accession=accession,
                        title=details["title"],
                        summary=details["summary"],
                        organism=organism,
                        data_type=data_type,
                        platform=details.get("platform"),
                        n_samples=n_samples,
                        conditions=conditions,
                        measurements=measurements,
                        normalized_bridge=normalized_bridge,
                    )

                    self.experiments[accession] = exp_doc
                    collected += 1
                    print(
                        f"   ✅ {accession}: {gene} ({len(measurements)} measurements)"
                    )

                time.sleep(0.5)  # Rate limiting

            time.sleep(1)  # Pause entre gènes

        if collected > 0:
            self._save()

        print(f"\n📊 GEO: {collected} nouveaux datasets")
        print(f"📊 Total: {len(self.experiments)} experiments")
        return collected


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    import tempfile

    # Test avec dossier temporaire
    with tempfile.TemporaryDirectory() as tmpdir:
        robot = RobotExperiments(tmpdir)

        # Test de collecte
        n = robot.collect(
            genes=["BRCA1", "TP53"],
            keywords=["breast", "cancer"],
            organism="Homo sapiens",
            max_per_gene=2,
        )

        print(f"\n✅ Test terminé: {n} experiments collectés")

        # Afficher un exemple
        if robot.experiments:
            exp = list(robot.experiments.values())[0]
            print(f"\n📋 Exemple:")
            print(f"   Accession: {exp.accession}")
            print(f"   Title: {exp.title[:80]}...")
            print(f"   Measurements: {len(exp.measurements)}")
            if exp.measurements:
                print(f"   Sample: {exp.measurements[0]}")
