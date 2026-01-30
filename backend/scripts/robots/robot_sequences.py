"""
🧬 ROBOT SEQUENCES - Collecte de protéines UniProt
==================================================
Adapté au schéma ProteinDocument
"""

import requests
import json
import time
import os
from typing import List, Dict, Optional

from app.models.schemas import ProteinDocument, NormalizedBridge


# ============================================================================
# PROCESSUS BIOLOGIQUES
# ============================================================================

BIOLOGICAL_PROCESSES = {
    "apoptosis", "autophagy", "cell cycle", "cell death",
    "cell proliferation", "cell differentiation",
    "dna repair", "transcription", "translation",
    "signal transduction", "phosphorylation",
    "immune response", "inflammation",
    "metabolism", "oxidative stress"
}


# ============================================================================
# ROBOT SEQUENCES
# ============================================================================

class RobotSequences:
    """
    Collecte de séquences protéiques depuis UniProt
    Output: ProteinDocument
    """
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.base_url = "https://rest.uniprot.org/uniprotkb/search"
        self.proteins = self._load_existing()
    
    
    def _load_existing(self) -> Dict[str, ProteinDocument]:
        """Charge les protéines existantes"""
        filepath = os.path.join(self.output_dir, "proteins.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {prot['uniprot_id']: ProteinDocument(**prot) for prot in data}
        return {}
    
    
    def _save(self):
        """Sauvegarde les protéines"""
        filepath = os.path.join(self.output_dir, "proteins.json")
        proteins = [prot.model_dump() for prot in self.proteins.values()]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(proteins, f, indent=2, ensure_ascii=False)
    
    
    def search_uniprot(self, query: str, organism: str = "human", max_results: int = 50) -> List[dict]:
        """Recherche UniProt"""
        print(f"🔍 Recherche UniProt: '{query}'...")
        
        # Mapper organism
        organism_map = {
            "human": "9606",
            "mouse": "10090",
            "rat": "10116"
        }
        tax_id = organism_map.get(organism.lower())
        
        # Query
        query_parts = [f'({query})']
        if tax_id:
            query_parts.append(f'(taxonomy_id:{tax_id})')
        
        full_query = " AND ".join(query_parts)
        
        # Paramètres
        params = {
            "query": full_query,
            "format": "json",
            "size": min(max_results, 100),
            "fields": "accession,id,protein_name,gene_names,organism_name,length,sequence,go,cc_function,cc_disease"
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=60)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                print(f"   ✅ {len(results)} protéines trouvées")
                return results
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
        
        return []
    
    
    def parse_entry(self, entry: dict) -> Optional[ProteinDocument]:
        """Parse une entrée UniProt"""
        try:
            # Accession / UniProt ID
            uniprot_id = entry.get("primaryAccession", "")
            if not uniprot_id:
                return None
            
            # Nom protéine
            protein_name = ""
            if "proteinDescription" in entry:
                desc = entry["proteinDescription"]
                rec = desc.get("recommendedName", {})
                if "fullName" in rec:
                    protein_name = rec["fullName"].get("value", "")
            
            # Gènes
            gene_names = []
            for gene in entry.get("genes", []):
                if "geneName" in gene:
                    name = gene["geneName"].get("value", "")
                    if name:
                        gene_names.append(name)
            
            # Organisme
            organism = entry.get("organism", {}).get("scientificName", "Homo sapiens")
            
            # Séquence
            sequence = entry.get("sequence", {}).get("value", "")
            if not sequence:
                return None
            
            # Fonction
            function = ""
            for comment in entry.get("comments", []):
                if comment.get("commentType") == "FUNCTION":
                    texts = comment.get("texts", [])
                    if texts:
                        function = texts[0].get("value", "")
                    break
            
            # GO terms - TOUS (pas de limite)
            go_terms = []
            for ref in entry.get("uniProtKBCrossReferences", []):
                if ref.get("database") == "GO":
                    go_id = ref.get("id", "")
                    if go_id:
                        go_terms.append(go_id)
            
            # Maladies
            diseases = []
            for comment in entry.get("comments", []):
                if comment.get("commentType") == "DISEASE":
                    disease = comment.get("disease", {})
                    name = disease.get("description", "")
                    if name:
                        diseases.append(name)
            
            # Détection de processus depuis la fonction
            processes = []
            if function:
                func_lower = function.lower()
                for proc in BIOLOGICAL_PROCESSES:
                    if proc in func_lower:
                        processes.append(proc)
            
            # Créer NormalizedBridge
            normalized_bridge = NormalizedBridge(
                genes=[g.upper() for g in gene_names],
                diseases=[d.lower() for d in diseases],
                processes=processes,
                keywords=["protein", organism.split()[0].lower()]
            )
            
            # Créer ProteinDocument
            return ProteinDocument(
                uniprot_id=uniprot_id,
                protein_name=protein_name,
                gene_names=gene_names,
                organism=organism,
                sequence=sequence,
                function=function,
                go_terms=go_terms,  # TOUS (pas de limite)
                diseases=diseases,
                normalized_bridge=normalized_bridge
            )
            
        except Exception as e:
            print(f"   ⚠️ Erreur parsing: {e}")
            return None
    
    
    def collect(self, query: str, organism: str = "human", max_results: int = 50) -> int:
        """
        Collecte des protéines
        Returns: nombre de nouvelles protéines
        """
        print(f"\n{'='*60}")
        print(f"🧬 ROBOT SEQUENCES - UniProt")
        print(f"{'='*60}")
        
        # Rechercher
        entries = self.search_uniprot(query, organism, max_results)
        if not entries:
            return 0
        
        # Parser
        collected = 0
        for entry in entries:
            prot_doc = self.parse_entry(entry)
            
            if prot_doc and prot_doc.uniprot_id not in self.proteins:
                self.proteins[prot_doc.uniprot_id] = prot_doc
                collected += 1
        
        if collected > 0:
            self._save()
        
        print(f"\n🆕 {collected} nouvelles protéines")
        print(f"📊 Total: {len(self.proteins)} protéines")
        return collected
