"""
🔬 ROBOT STRUCTURES - Collecte de structures 3D PDB + AlphaFold
===============================================================
Adapté au schéma StructureDocument - Collecte PDB ET AlphaFold
"""

import requests
import json
import time
import os
from typing import List, Dict, Optional

from app.models.schemas import StructureDocument, NormalizedBridge


# ============================================================================
# ROBOT STRUCTURES
# ============================================================================


class RobotStructures:
    """
    Collecte de structures 3D depuis PDB ET AlphaFold
    Output: StructureDocument (les deux types dans le même fichier)
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "structures_pdb"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "structures_alphafold"), exist_ok=True)

        # URLs PDB
        self.search_url = "https://search.rcsb.org/rcsbsearch/v2/query"
        self.data_url = "https://data.rcsb.org/rest/v1/core/entry"
        self.download_url = "https://files.rcsb.org/download"

        # URLs AlphaFold
        self.alphafold_api = "https://alphafold.ebi.ac.uk/api"

        self.structures = self._load_existing()

    def _load_existing(self) -> Dict[str, StructureDocument]:
        """Charge les structures existantes (PDB + AlphaFold)"""
        filepath = os.path.join(self.output_dir, "structures.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Index par pdb_id OU alphafold_id AVEC préfixe
                result = {}
                for struct in data:
                    struct_doc = StructureDocument(**struct)
                    # Utiliser préfixe pour éviter collisions
                    if struct_doc.pdb_id:
                        key = f"pdb_{struct_doc.pdb_id}"
                    elif struct_doc.alphafold_id:
                        key = f"af_{struct_doc.alphafold_id}"
                    else:
                        continue
                    result[key] = struct_doc
                return result
        return {}

    def _save(self):
        """Sauvegarde les structures (PDB + AlphaFold ensemble)"""
        filepath = os.path.join(self.output_dir, "structures.json")
        structures = [struct.model_dump() for struct in self.structures.values()]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(structures, f, indent=2, ensure_ascii=False)

    # ========================================================================
    # PDB - Structures Expérimentales
    # ========================================================================

    def search_pdb(self, query: str, max_results: int = 30) -> List[str]:
        """Recherche des structures PDB"""
        print(f"🔍 Recherche PDB: '{query}'...")

        search_query = {
            "query": {
                "type": "terminal",
                "service": "full_text",
                "parameters": {"value": query},
            },
            "return_type": "entry",
            "request_options": {"paginate": {"start": 0, "rows": max_results}},
        }

        try:
            response = requests.post(
                self.search_url,
                json=search_query,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                pdb_ids = []

                for item in data.get("result_set", []):
                    if isinstance(item, dict):
                        pdb_id = item.get("identifier", "")
                    else:
                        pdb_id = str(item)

                    if pdb_id:
                        pdb_ids.append(pdb_id)

                print(f"   ✅ {len(pdb_ids)} structures PDB trouvées")
                return pdb_ids
        except Exception as e:
            print(f"   ❌ Erreur: {e}")

        return []

    def download_pdb_file(self, pdb_id: str) -> Optional[str]:
        """Télécharge un fichier PDB"""
        file_path = os.path.join(self.output_dir, "structures_pdb", f"{pdb_id}.pdb")

        if os.path.exists(file_path):
            return file_path

        url = f"{self.download_url}/{pdb_id}.pdb"

        try:
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(response.content)
                return file_path
        except:
            pass

        return None

    def get_pdb_details(self, pdb_id: str) -> Optional[dict]:
        """Obtient les détails d'une structure PDB"""
        try:
            url = f"{self.data_url}/{pdb_id}"
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                return response.json()
        except:
            pass

        return None

    def parse_pdb_structure(self, pdb_id: str) -> Optional[StructureDocument]:
        """Parse une structure PDB et crée StructureDocument"""

        # Télécharger le fichier
        file_path = self.download_pdb_file(pdb_id)

        # Obtenir métadonnées
        data = self.get_pdb_details(pdb_id)

        if not data:
            # Métadonnées minimales
            return StructureDocument(
                pdb_id=pdb_id, title=f"Structure {pdb_id}", file_path=file_path
            )

        # Titre
        title = ""
        struct = data.get("struct", {})
        if isinstance(struct, dict):
            title = struct.get("title", "")

        # Méthode
        method = ""
        exptl = data.get("exptl", [])
        if exptl and isinstance(exptl, list) and len(exptl) > 0:
            if isinstance(exptl[0], dict):
                method = exptl[0].get("method", "")

        # Résolution
        resolution = None
        entry_info = data.get("rcsb_entry_info", {})
        if isinstance(entry_info, dict):
            res_list = entry_info.get("resolution_combined", [])
            if res_list:
                resolution = res_list[0]

        # UniProt IDs
        uniprot_ids = []
        polymer_entities = data.get("polymer_entities", [])
        if isinstance(polymer_entities, list):
            for entity in polymer_entities:
                if not isinstance(entity, dict):
                    continue

                container = entity.get("rcsb_polymer_entity_container_identifiers", {})
                if isinstance(container, dict):
                    refs = container.get("reference_sequence_identifiers", [])
                    if isinstance(refs, list):
                        for ref in refs:
                            if (
                                isinstance(ref, dict)
                                and ref.get("database_name") == "UniProt"
                            ):
                                uid = ref.get("database_accession", "")
                                if uid and uid not in uniprot_ids:
                                    uniprot_ids.append(uid)

        # Ligands
        ligands = []
        nonpoly = data.get("nonpolymer_entities", [])
        if isinstance(nonpoly, list):
            for lig in nonpoly:
                if isinstance(lig, dict):
                    comp = lig.get("nonpolymer_comp", {})
                    if isinstance(comp, dict):
                        chem = comp.get("chem_comp", {})
                        if isinstance(chem, dict):
                            lig_id = chem.get("id", "")
                            if lig_id:
                                ligands.append(lig_id)

        # Créer NormalizedBridge (basique pour PDB)
        normalized_bridge = NormalizedBridge(
            keywords=["structure", "3d", "pdb", "experimental"]
        )

        # Créer StructureDocument pour PDB
        return StructureDocument(
            pdb_id=pdb_id,
            alphafold_id=None,  # PDB = pas d'alphafold_id
            title=title,
            method=method,
            resolution=resolution,
            uniprot_ids=uniprot_ids,
            chains=[],  # Nécessite parsing du fichier PDB
            ligands=ligands,
            file_path=file_path,
            normalized_bridge=normalized_bridge,
        )

    # ========================================================================
    # AlphaFold - Structures Prédites
    # ========================================================================

    def download_alphafold_for_uniprot(
        self, uniprot_id: str
    ) -> Optional[StructureDocument]:
        """Télécharge structure AlphaFold pour un UniProt ID"""

        try:
            # 1. Obtenir les métadonnées AlphaFold
            url = f"{self.alphafold_api}/prediction/{uniprot_id}"
            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                return None

            data = response.json()
            if not data:
                return None

            entry = data[0] if isinstance(data, list) else data

            alphafold_id = entry.get("entryId", "")
            if not alphafold_id:
                return None

            # Vérifier si déjà existant
            if alphafold_id in self.structures:
                return None

            # 2. Télécharger le fichier PDB
            pdb_url = entry.get("pdbUrl", "")
            local_path = None

            if pdb_url:
                local_path = os.path.join(
                    self.output_dir, "structures_alphafold", f"{uniprot_id}.pdb"
                )

                if not os.path.exists(local_path):
                    try:
                        pdb_response = requests.get(pdb_url, timeout=60)
                        if pdb_response.status_code == 200:
                            with open(local_path, "wb") as f:
                                f.write(pdb_response.content)
                    except:
                        local_path = None

            # 3. Créer NormalizedBridge
            gene_name = entry.get("gene", "")
            normalized_bridge = NormalizedBridge(
                genes=[gene_name.upper()] if gene_name else [],
                keywords=["structure", "3d", "alphafold", "predicted"],
            )

            # 4. Créer StructureDocument pour AlphaFold
            return StructureDocument(
                pdb_id=None,  # AlphaFold = pas de pdb_id
                alphafold_id=alphafold_id,
                title=f"AlphaFold prediction: {entry.get('uniprotDescription', uniprot_id)}",
                method="predicted",
                resolution=None,  # AlphaFold n'a pas de résolution
                uniprot_ids=[uniprot_id],
                chains=[],
                ligands=[],
                file_path=local_path,
                normalized_bridge=normalized_bridge,
            )

        except Exception as e:
            print(f"   ⚠️ AlphaFold {uniprot_id}: {e}")
            return None

    # ========================================================================
    # Collecte AlphaFold depuis proteins.json
    # ========================================================================

    def collect_alphafold_from_proteins(self, max_structures: int = 100) -> int:
        """
        Collecte AlphaFold depuis les protéines déjà collectées (proteins.json)

        Returns:
            Nombre de nouvelles structures AlphaFold
        """
        print(f"\n{'='*60}")
        print(f"🤖 ROBOT ALPHAFOLD - Depuis proteins.json")
        print(f"{'='*60}")

        # 1. Charger proteins.json
        proteins_file = os.path.join(self.output_dir, "proteins.json")
        if not os.path.exists(proteins_file):
            print(f"\n❌ Fichier proteins.json non trouvé")
            print(
                f"   Lancez d'abord: python data_collect.py --query 'BRCA1' --sequences"
            )
            return 0

        try:
            with open(proteins_file, "r", encoding="utf-8") as f:
                proteins = json.load(f)
        except Exception as e:
            print(f"❌ Erreur lecture proteins.json: {e}")
            return 0

        # 2. Extraire UniProt IDs
        all_uniprot_ids = [p["uniprot_id"] for p in proteins if p.get("uniprot_id")]

        # 3. Filtrer ceux déjà téléchargés
        new_uniprot_ids = []
        for uid in all_uniprot_ids:
            # Chercher si déjà existant
            already_exists = any(
                s.alphafold_id and uid in s.uniprot_ids
                for s in self.structures.values()
                if s.alphafold_id
            )
            if not already_exists:
                new_uniprot_ids.append(uid)

        new_uniprot_ids = new_uniprot_ids[:max_structures]

        print(f"\n📊 {len(all_uniprot_ids)} protéines dans proteins.json")
        print(f"🆕 {len(new_uniprot_ids)} nouvelles à télécharger")

        if not new_uniprot_ids:
            print("   ✅ Toutes déjà téléchargées")
            return 0

        # 4. Télécharger AlphaFold
        collected = 0
        print(f"\n📥 Téléchargement AlphaFold...")

        for i, uniprot_id in enumerate(new_uniprot_ids):
            struct_doc = self.download_alphafold_for_uniprot(uniprot_id)

            if struct_doc and struct_doc.alphafold_id:
                key = f"af_{struct_doc.alphafold_id}"
                self.structures[key] = struct_doc
                collected += 1
                print(f"   ✅ AlphaFold: {uniprot_id}")

            if (i + 1) % 5 == 0:
                print(f"   {i + 1}/{len(new_uniprot_ids)} traités")

            time.sleep(0.3)

        # 5. Sauvegarder
        if collected > 0:
            self._save()

        # 6. Stats
        af_count = sum(1 for s in self.structures.values() if s.alphafold_id)

        print(f"\n{'='*60}")
        print(f"🆕 {collected} nouvelles structures AlphaFold")
        print(f"📊 Total AlphaFold: {af_count}")
        print(f"📊 Total structures: {len(self.structures)}")
        print(f"{'='*60}")

        return collected

    # ========================================================================
    # Collecte Principale (PDB + AlphaFold)
    # ========================================================================

    def collect(
        self, query: str, max_results: int = 30, include_alphafold: bool = False
    ) -> int:
        """
        Collecte des structures 3D - PDB seulement

        Args:
            query: Requête de recherche
            max_results: Nombre max de structures PDB
            include_alphafold: Si True, télécharge aussi AlphaFold (désactivé par défaut)

        Returns: nombre de nouvelles structures PDB
        """
        print(f"\n{'='*60}")
        print(f"🔬 ROBOT STRUCTURES - PDB")
        print(f"{'='*60}")

        collected = 0
        uniprot_ids_found = set()

        # ====================================================================
        # 1. COLLECTER PDB
        # ====================================================================
        print(f"\n📍 Collecte PDB...")
        pdb_ids = self.search_pdb(query, max_results)
        if not pdb_ids:
            print("❌ Aucune structure PDB trouvée")
            return 0

        print(f"\n📥 Téléchargement PDB...")
        for i, pdb_id in enumerate(pdb_ids):
            # Vérifier avec préfixe
            key = f"pdb_{pdb_id}"
            if key in self.structures:
                continue

            struct_doc = self.parse_pdb_structure(pdb_id)

            if struct_doc:
                # Sauvegarder structure PDB avec préfixe
                self.structures[key] = struct_doc
                collected += 1
                print(f"   ✅ PDB {pdb_id}")

                # Collecter les UniProt IDs pour AlphaFold (si activé)
                if include_alphafold:
                    uniprot_ids_found.update(struct_doc.uniprot_ids)

            if (i + 1) % 5 == 0:
                print(f"   {i + 1}/{len(pdb_ids)} structures PDB traitées")

            time.sleep(0.3)

        # ====================================================================
        # 2. COLLECTER ALPHAFOLD (optionnel, désactivé par défaut)
        # ====================================================================
        if include_alphafold and uniprot_ids_found:
            print(
                f"\n📥 Téléchargement AlphaFold ({len(uniprot_ids_found)} protéines)..."
            )

            for uniprot_id in uniprot_ids_found:
                # Vérifier si déjà existant (avec préfixe provisoire)
                key_temp = f"af_{uniprot_id}"
                if key_temp in self.structures:
                    continue

                # Utiliser le bon nom de méthode
                alphafold_struct = self.download_alphafold_for_uniprot(uniprot_id)

                if alphafold_struct and alphafold_struct.alphafold_id:
                    # Utiliser alphafold_id comme clé
                    key = f"af_{alphafold_struct.alphafold_id}"
                    self.structures[key] = alphafold_struct
                    collected += 1
                    print(f"   ✅ AlphaFold {uniprot_id}")

                time.sleep(0.3)

        # ====================================================================
        # 3. SAUVEGARDER
        # ====================================================================
        if collected > 0:
            self._save()

        # ====================================================================
        # 4. STATISTIQUES
        # ====================================================================
        pdb_count = sum(1 for s in self.structures.values() if s.pdb_id)
        af_count = sum(1 for s in self.structures.values() if s.alphafold_id)

        print(f"\n{'='*60}")
        print(f"🆕 {collected} nouvelles structures")
        print(f"📊 Total PDB: {pdb_count}")
        print(f"📊 Total AlphaFold: {af_count}")
        print(f"📊 Total: {len(self.structures)} structures")
        print(f"{'='*60}")

        return collected
