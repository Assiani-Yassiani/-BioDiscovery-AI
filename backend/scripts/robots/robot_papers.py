"""
📄 ROBOT PAPERS - Collecte d'articles PubMed
============================================
Adapté au schéma ArticleDocument
"""

import requests
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from xml.etree import ElementTree
import os
import re

from app.models.schemas import ArticleDocument, NormalizedBridge


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    PUBTATOR_EXPORT = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson"
    
    PUBMED_DELAY = 0.34
    PUBTATOR_DELAY = 0.5


# Gènes connus - LISTE COMPLÈTE
KNOWN_GENES = {
    "TP53", "P53", "BRCA1", "BRCA2", "EGFR", "HER2", "ERBB2", "KRAS", "NRAS",
    "BRAF", "PIK3CA", "PTEN", "AKT1", "MTOR", "MDM2", "MDM4", "RB1", "APC",
    "VHL", "NF1", "NF2", "MEN1", "RET", "KIT", "PDGFRA", "ALK", "ROS1",
    "MET", "FGFR1", "FGFR2", "FGFR3", "CDK4", "CDK6", "CCND1",
    "ATM", "ATR", "CHEK1", "CHEK2", "PALB2", "RAD51", "MLH1", "MSH2",
    "BCL2", "BAX", "BAK", "CASP3", "CASP8", "CASP9", "APAF1",
    "CD274", "PDCD1", "CTLA4", "CD16A", "FCGR3A",
    "JAK1", "JAK2", "STAT3", "SRC", "ABL1", "BCR",
    "MYC", "MYCN", "NOTCH1", "SMO", "GLI1",
    "ESR1", "AR", "GFAP", "VEGF", "VEGFA", "TNF", "IL6", "IL1B",
    "TGFB1", "SMAD4", "TP73", "CDKN2A", "CDKN1A",
    "ATP1A2", "HSD11B1", "SOD1", "APP", "MAPT", "SNCA", "HTT",
    "ACE2", "TMPRSS2", "CD4", "CCR5", "CXCR4",
}

# Processus biologiques - LISTE COMPLÈTE
BIOLOGICAL_PROCESSES = {
    "apoptosis", "autophagy", "necrosis", "cell death",
    "cell cycle", "cell division", "mitosis",
    "cell proliferation", "cell growth",
    "cell differentiation", "cell migration", "metastasis",
    "dna repair", "dna damage", "dna replication",
    "transcription", "gene expression", "translation",
    "signal transduction", "signaling pathway",
    "phosphorylation", "kinase", "phosphatase",
    "immune response", "inflammation", "cytokine",
    "angiogenesis", "metabolism", "glycolysis",
    "oxidative stress", "tumor suppressor", "oncogene",
}

# Mappings MeSH → GO
MESH_TO_GO = {
    "Apoptosis": ["GO:0006915"],
    "Autophagy": ["GO:0006914"],
    "Cell Cycle": ["GO:0007049"],
    "Cell Proliferation": ["GO:0008283"],
    "DNA Repair": ["GO:0006281"],
    "Signal Transduction": ["GO:0007165"],
    "Phosphorylation": ["GO:0016310"],
    "Immune Response": ["GO:0006955"],
    "Inflammation": ["GO:0006954"],
    "Angiogenesis": ["GO:0001525"],
    "Cell Migration": ["GO:0016477"],
    "Cell Differentiation": ["GO:0030154"],
    "Transcription, Genetic": ["GO:0006351"],
    "Translation": ["GO:0006412"],
    "Protein Folding": ["GO:0006457"],
    "Oxidative Stress": ["GO:0006979"],
}

# Maladies normalisées
MESH_DISEASE_NORMALIZE = {
    "Neoplasms": "cancer",
    "Breast Neoplasms": "breast cancer",
    "Lung Neoplasms": "lung cancer",
    "Colorectal Neoplasms": "colorectal cancer",
    "Prostatic Neoplasms": "prostate cancer",
    "Ovarian Neoplasms": "ovarian cancer",
    "Pancreatic Neoplasms": "pancreatic cancer",
    "Melanoma": "melanoma",
    "Leukemia": "leukemia",
    "Lymphoma": "lymphoma",
    "Glioblastoma": "glioblastoma",
    "Carcinoma": "carcinoma",
    "Adenocarcinoma": "adenocarcinoma",
    "Alzheimer Disease": "alzheimer disease",
    "Parkinson Disease": "parkinson disease",
    "Diabetes Mellitus": "diabetes",
    "Cardiovascular Diseases": "cardiovascular disease",
}

# Pathways KEGG
PATHWAYS_MAP = {
    "p53": ["hsa04115"],
    "pi3k": ["hsa04151"],
    "mapk": ["hsa04010"],
    "wnt": ["hsa04310"],
    "apoptosis": ["hsa04210"],
}


# ============================================================================
# ROBOT PAPERS
# ============================================================================

class RobotPapers:
    """
    Collecte automatique d'articles depuis PubMed
    Output: ArticleDocument
    """
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.articles = self._load_existing()
    
    
    def _load_existing(self) -> Dict[str, ArticleDocument]:
        """Charge les articles existants"""
        filepath = os.path.join(self.output_dir, "articles.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {a['pmid']: ArticleDocument(**a) for a in data}
        return {}
    
    
    def _save(self):
        """Sauvegarde les articles"""
        filepath = os.path.join(self.output_dir, "articles.json")
        articles = [a.model_dump() for a in self.articles.values()]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(articles, f, indent=2, ensure_ascii=False)
    
    
    def search_pubmed(self, query: str, max_results: int = 100) -> List[str]:
        """Recherche des PMIDs"""
        print(f"🔍 Recherche PubMed: '{query}'...")
        
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "pub_date"
        }
        
        try:
            response = requests.get(Config.PUBMED_SEARCH, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])
            print(f"   ✅ {len(pmids)} articles trouvés")
            return pmids
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            return []
    
    
    def download_details(self, pmids: List[str]) -> List[dict]:
        """Télécharge les détails PubMed"""
        if not pmids:
            return []
        
        print(f"📥 Téléchargement ({len(pmids)} articles)...")
        articles = []
        batch_size = 50
        
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i:i + batch_size]
            
            params = {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml"
            }
            
            try:
                response = requests.get(Config.PUBMED_FETCH, params=params, timeout=30)
                response.raise_for_status()
                batch_articles = self._parse_xml(response.content)
                articles.extend(batch_articles)
                print(f"   Batch {i//batch_size + 1}: OK")
                time.sleep(Config.PUBMED_DELAY)
            except Exception as e:
                print(f"   ❌ Erreur batch: {e}")
        
        return articles
    
    
    def _parse_xml(self, xml_content: bytes) -> List[dict]:
        """Parse le XML PubMed"""
        articles = []
        try:
            root = ElementTree.fromstring(xml_content)
            for elem in root.findall(".//PubmedArticle"):
                article = self._extract_article(elem)
                if article:
                    articles.append(article)
        except Exception as e:
            print(f"   ⚠️ Erreur parsing: {e}")
        return articles
    
    
    def _extract_article(self, elem) -> Optional[dict]:
        """Extrait un article du XML"""
        try:
            # PMID
            pmid_elem = elem.find(".//PMID")
            if pmid_elem is None or not pmid_elem.text:
                return None
            
            # Titre
            title_elem = elem.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None and title_elem.text else ""
            
            # Abstract
            abstract_parts = []
            for ab in elem.findall(".//AbstractText"):
                if ab.text:
                    label = ab.get("Label", "")
                    text = f"{label}: {ab.text}" if label else ab.text
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts) if abstract_parts else ""
            
            # Auteurs
            authors = []
            for author in elem.findall(".//Author"):
                lastname = author.find("LastName")
                forename = author.find("ForeName")
                if lastname is not None and lastname.text:
                    name = lastname.text
                    if forename is not None and forename.text:
                        name = f"{forename.text} {name}"
                    authors.append(name)
            
            # Journal, Année
            journal_elem = elem.find(".//Journal/Title")
            year_elem = elem.find(".//PubDate/Year")
            
            # DOI
            doi = None
            for article_id in elem.findall(".//ArticleId"):
                if article_id.get("IdType") == "doi" and article_id.text:
                    doi = article_id.text
                    break
            
            # MeSH terms
            mesh_terms = [m.text for m in elem.findall(".//MeshHeading/DescriptorName") if m.text]
            
            # Keywords
            keywords = [k.text for k in elem.findall(".//Keyword") if k.text]
            
            return {
                "pmid": pmid_elem.text,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "journal": journal_elem.text if journal_elem is not None else None,
                "year": int(year_elem.text) if year_elem is not None and year_elem.text else None,
                "doi": doi,
                "mesh_terms": mesh_terms,
                "keywords": keywords,
            }
            
        except Exception as e:
            print(f"   ⚠️ Erreur extraction: {e}")
            return None
    
    
    def enrich_with_pubtator(self, articles: List[dict]) -> List[ArticleDocument]:
        """Enrichit avec PubTator et crée NormalizedBridge"""
        print(f"🧬 Enrichissement ({len(articles)} articles)...")
        
        # Appel PubTator
        pmids = [a["pmid"] for a in articles]
        pubtator_data = self._call_pubtator(pmids)
        
        # Index par PMID
        pubtator_index = {}
        for entry in pubtator_data:
            pmid = str(entry.get("pmid", entry.get("id", "")))
            pubtator_index[pmid] = entry
        
        # Enrichir
        enriched = []
        for article in articles:
            try:
                doc = self._create_article_document(
                    article,
                    pubtator_index.get(article["pmid"], {})
                )
                enriched.append(doc)
            except Exception as e:
                print(f"   ⚠️ Erreur {article['pmid']}: {e}")
        
        return enriched
    
    
    def _call_pubtator(self, pmids: List[str]) -> List[dict]:
        """Appelle PubTator en batch"""
        results = []
        batch_size = 100
        
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i:i + batch_size]
            
            try:
                pmids_str = ",".join(batch)
                url = f"{Config.PUBTATOR_EXPORT}?pmids={pmids_str}"
                response = requests.get(url, timeout=60)
                
                if response.status_code == 200 and response.text.strip():
                    for line in response.text.strip().split("\n"):
                        if line.strip():
                            try:
                                results.append(json.loads(line))
                            except:
                                pass
                
                time.sleep(Config.PUBTATOR_DELAY)
            except Exception as e:
                print(f"   ⚠️ PubTator: {e}")
        
        return results
    
    
    def _create_article_document(self, article: dict, pubtator_entry: dict) -> ArticleDocument:
        """Crée un ArticleDocument avec NormalizedBridge"""
        
        # Texte complet
        title = article.get("title") or ""
        abstract = article.get("abstract") or ""
        full_text = title + " " + abstract
        
        # Extraction PubTator
        pubtator_genes = self._extract_genes_pubtator(pubtator_entry)
        pubtator_diseases = self._extract_diseases_pubtator(pubtator_entry)
        
        # Extraction locale (backup)
        local_genes = self._extract_genes_local(full_text, article.get("keywords", []))
        local_diseases = self._extract_diseases_local(article.get("mesh_terms", []), full_text)
        
        # Fusion - GARDER TOUT (pas de limite)
        genes = list(set(pubtator_genes + local_genes))
        diseases = list(set(pubtator_diseases + local_diseases))
        
        # Processus biologiques
        processes = self._detect_processes(full_text)
        
        # Pathways
        pathways = self._detect_pathways(full_text, genes)
        
        # Keywords - TOUS les MeSH terms (pas de limite)
        keywords = article.get("mesh_terms", [])
        
        # Créer NormalizedBridge
        normalized_bridge = NormalizedBridge(
            genes=[g.upper() for g in genes],
            diseases=[d.lower() for d in diseases],
            processes=processes,
            pathways=pathways,
            keywords=keywords
        )
        
        # Créer ArticleDocument
        return ArticleDocument(
            pmid=article["pmid"],
            title=article["title"],
            abstract=article["abstract"],
            authors=article.get("authors", []),
            journal=article.get("journal"),
            year=article.get("year"),
            doi=article.get("doi"),
            mesh_terms=article.get("mesh_terms", []),
            normalized_bridge=normalized_bridge
        )
    
    
    def _extract_genes_pubtator(self, entry: dict) -> List[str]:
        """Extrait gènes depuis PubTator"""
        genes = []
        for passage in entry.get("passages", []):
            for annot in passage.get("annotations", []):
                entity_type = annot.get("infons", {}).get("type", "").lower()
                text = annot.get("text", "")
                if entity_type in ["gene", "protein"] and text:
                    genes.append(text.upper())
        return list(set(genes))
    
    
    def _extract_diseases_pubtator(self, entry: dict) -> List[str]:
        """Extrait maladies depuis PubTator"""
        diseases = []
        for passage in entry.get("passages", []):
            for annot in passage.get("annotations", []):
                entity_type = annot.get("infons", {}).get("type", "").lower()
                text = annot.get("text", "")
                if entity_type == "disease" and text:
                    diseases.append(text.lower())
        return list(set(diseases))
    
    
    def _extract_genes_local(self, text: str, keywords: list = None) -> List[str]:
        """Extraction locale de gènes - COMPLÈTE avec keywords"""
        genes = []
        text_upper = text.upper()
        
        # 1. Gènes connus dans le texte
        for gene in KNOWN_GENES:
            if gene in text_upper:
                genes.append(gene)
        
        # 2. Gènes depuis keywords (format court: 2-6 lettres/chiffres)
        if keywords:
            for kw in keywords:
                kw_upper = kw.upper().strip()
                # Pattern pour gènes: commence par lettre, 1-6 caractères alphanumériques
                if re.match(r'^[A-Z][A-Z0-9]{1,6}$', kw_upper):
                    # Exclure acronymes génériques
                    if kw_upper not in ["DNA", "RNA", "ATP", "GTP", "PCR", "MRI", "CT", "FISH"]:
                        genes.append(kw_upper)
        
        return genes
    
    
    def _extract_diseases_local(self, mesh_terms: list, full_text: str = "") -> List[str]:
        """Extraction locale de maladies - COMPLÈTE avec patterns"""
        diseases = []
        
        # 1. Maladies depuis MeSH avec normalisation
        for mesh in mesh_terms:
            if mesh in MESH_DISEASE_NORMALIZE:
                diseases.append(MESH_DISEASE_NORMALIZE[mesh])
            elif any(t in mesh.lower() for t in ["cancer", "tumor", "carcinoma", "neoplasm", "disease"]):
                diseases.append(mesh.lower())
        
        # 2. Maladies depuis texte avec patterns
        if full_text:
            disease_patterns = [
                ("breast cancer", ["breast cancer", "breast carcinoma"]),
                ("lung cancer", ["lung cancer", "lung carcinoma", "nsclc"]),
                ("colon cancer", ["colon cancer", "colorectal cancer"]),
                ("prostate cancer", ["prostate cancer"]),
                ("leukemia", ["leukemia", "leukaemia"]),
                ("melanoma", ["melanoma"]),
                ("glioblastoma", ["glioblastoma", "gbm"]),
                ("ovarian cancer", ["ovarian cancer"]),
                ("pancreatic cancer", ["pancreatic cancer"]),
            ]
            
            text_lower = full_text.lower()
            for disease, patterns in disease_patterns:
                for pattern in patterns:
                    if pattern in text_lower:
                        diseases.append(disease)
                        break
        
        return diseases
    
    
    def _detect_processes(self, text: str) -> List[str]:
        """Détecte les processus biologiques"""
        processes = []
        text_lower = text.lower()
        for proc in BIOLOGICAL_PROCESSES:
            if proc in text_lower:
                processes.append(proc)
        return list(set(processes))
    
    
    def _detect_pathways(self, text: str, genes: list) -> List[str]:
        """Détecte les pathways KEGG"""
        pathways = []
        text_lower = text.lower()
        genes_upper = [g.upper() for g in genes]
        
        for keyword, kegg_ids in PATHWAYS_MAP.items():
            if keyword in text_lower or keyword.upper() in genes_upper:
                pathways.extend(kegg_ids)
        
        return list(set(pathways))
    
    
    def collect(self, query: str, max_results: int = 100) -> int:
        """
        Collecte complète
        Returns: nombre de nouveaux articles
        """
        print(f"\n{'='*60}")
        print(f"📄 ROBOT PAPERS - {query}")
        print(f"{'='*60}")
        
        # Recherche
        pmids = self.search_pubmed(query, max_results)
        if not pmids:
            return 0
        
        # Téléchargement
        articles = self.download_details(pmids)
        if not articles:
            return 0
        
        # Enrichissement
        enriched = self.enrich_with_pubtator(articles)
        
        # Filtrer nouveaux
        new_articles = [a for a in enriched if a.pmid not in self.articles]
        print(f"\n🆕 {len(new_articles)} nouveaux articles")
        
        # Ajouter
        for article in new_articles:
            self.articles[article.pmid] = article
        
        if new_articles:
            self._save()
        
        print(f"📊 Total: {len(self.articles)} articles")
        return len(new_articles)
