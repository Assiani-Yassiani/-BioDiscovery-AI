"""
🖼️ ROBOT IMAGES - Collecte d'images KEGG Pathways
==================================================
Adapté au schéma ImageDocument
"""

import requests
import json
import time
import os
from datetime import datetime
from typing import List, Dict

from app.models.schemas import ImageDocument, NormalizedBridge


# ============================================================================
# PATHWAYS KEGG CONNUS
# ============================================================================

KEGG_PATHWAYS = {
    "hsa05200": {"name": "Pathways in cancer", "genes": ["TP53", "KRAS", "EGFR"]},
    "hsa05210": {"name": "Colorectal cancer", "genes": ["APC", "KRAS", "TP53"]},
    "hsa05224": {"name": "Breast cancer", "genes": ["BRCA1", "BRCA2", "ERBB2"]},
    "hsa04110": {"name": "Cell cycle", "genes": ["TP53", "RB1", "CDK4"]},
    "hsa04210": {"name": "Apoptosis", "genes": ["TP53", "BAX", "BCL2"]},
    "hsa04151": {"name": "PI3K-Akt signaling", "genes": ["PIK3CA", "AKT1", "PTEN"]},
    "hsa04010": {"name": "MAPK signaling", "genes": ["KRAS", "BRAF", "ERK"]},
}


# ============================================================================
# ROBOT IMAGES KEGG
# ============================================================================

class RobotImages:
    """
    Collecte d'images de pathways KEGG
    Output: ImageDocument
    """
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "images"), exist_ok=True)
        self.images = self._load_existing()
    
    
    def _load_existing(self) -> Dict[str, ImageDocument]:
        """Charge les images existantes"""
        filepath = os.path.join(self.output_dir, "images.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Créer un ID unique basé sur source + file_path
                return {self._make_id(img): ImageDocument(**img) for img in data}
        return {}
    
    
    def _make_id(self, img_data: dict) -> str:
        """Crée un ID unique pour une image"""
        return f"{img_data['source']}_{os.path.basename(img_data['file_path'])}"
    
    
    def _save(self):
        """Sauvegarde les images"""
        filepath = os.path.join(self.output_dir, "images.json")
        images = [img.model_dump() for img in self.images.values()]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(images, f, indent=2, ensure_ascii=False)
    
    
    def download_pathway(self, pathway_id: str, info: dict) -> bool:
        """Télécharge un pathway KEGG"""
        
        # Chemin local
        filename = f"{pathway_id}.png"
        file_path = os.path.join(self.output_dir, "images", filename)
        
        # Vérifier si déjà téléchargé
        img_id = f"kegg_{filename}"
        if img_id in self.images:
            return False
        
        # URL et téléchargement
        url = f"https://www.kegg.jp/kegg/pathway/hsa/{pathway_id}.png"
        
        try:
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                # Créer NormalizedBridge
                normalized_bridge = NormalizedBridge(
                    genes=[g.upper() for g in info["genes"]],
                    pathways=[pathway_id],
                    keywords=["pathway", "cancer"] if "cancer" in info["name"].lower() else ["pathway"]
                )
                
                # Créer ImageDocument
                img_doc = ImageDocument(
                    source="kegg",
                    image_type="pathway",
                    file_path=file_path,
                    url=url,
                    caption=f"KEGG Pathway: {info['name']}",
                    description=f"Pathway diagram for {info['name']} ({pathway_id})",
                    normalized_bridge=normalized_bridge
                )
                
                self.images[img_id] = img_doc
                return True
            
        except Exception as e:
            print(f"   ❌ {pathway_id}: {e}")
        
        return False
    
    
    def collect(self) -> int:
        """
        Collecte tous les pathways KEGG
        Returns: nombre de nouvelles images
        """
        print(f"\n{'='*60}")
        print(f"🖼️ ROBOT IMAGES - KEGG Pathways")
        print(f"{'='*60}")
        
        downloaded = 0
        
        for pathway_id, info in KEGG_PATHWAYS.items():
            if self.download_pathway(pathway_id, info):
                downloaded += 1
                print(f"   ✅ {pathway_id}: {info['name']}")
            else:
                print(f"   ⏭️ {pathway_id}: déjà en base")
            
            time.sleep(0.3)
        
        if downloaded > 0:
            self._save()
        
        print(f"\n📊 Total: {len(self.images)} images")
        return downloaded
