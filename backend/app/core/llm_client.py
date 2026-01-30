"""
Gemini LLM Client for BioDiscovery AI
Architecture v3.0 - With Bridge Cross-Modal Function

Features:
- bridge_cross_modal(): Génère queries + filters + alignment
- generate_design_candidates(): Design Assistant
- generate_summary(): Summary generation
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GeminiClient:
    """Client for Gemini LLM with Bridge and Design Assistant"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.model = None
        self.mock_mode = False
        
        if settings.gemini_api_key:
            try:
                # Try new API first
                try:
                    from google import genai
                    self.client = genai.Client(api_key=settings.gemini_api_key)
                    self.model_name = settings.gemini_model
                    self.use_new_api = True
                    logger.info(f"✅ Gemini client initialized (new API), model: {self.model_name}")
                except ImportError:
                    # Fallback to old API
                    import google.generativeai as genai
                    genai.configure(api_key=settings.gemini_api_key)
                    self.model = genai.GenerativeModel(settings.gemini_model)
                    self.use_new_api = False
                    logger.info(f"✅ Gemini client initialized (old API), model: {settings.gemini_model}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Gemini: {e}. Using mock mode.")
                self.mock_mode = True
        else:
            logger.warning("⚠️ No Gemini API key provided. Using mock mode.")
            self.mock_mode = True
        
        self._initialized = True
    
    async def generate(self, prompt: str) -> str:
        """Generate response from Gemini"""
        if self.mock_mode:
            return self._mock_response(prompt)
        
        try:
            if self.use_new_api:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )
                return response.text
            else:
                response = self.model.generate_content(prompt)
                return response.text
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            return self._mock_response(prompt)
    
    def _mock_response(self, prompt: str) -> str:
        """Generate mock response - uses actual user query when available"""
        prompt_lower = prompt.lower()
        
        # Extract user query from prompt if present
        user_query = None
        if "USER QUERY:" in prompt:
            try:
                start = prompt.index("USER QUERY:") + len("USER QUERY:")
                end = prompt.find("\n", start)
                user_query = prompt[start:end].strip() if end > start else prompt[start:].strip()
                logger.info(f"📝 Mock: Extracted user query: '{user_query}'")
            except:
                pass
        
        # Extract gene names from prompt or metadata
        extracted_genes = []
        gene_patterns = ["BRCA1", "BRCA2", "TP53", "EGFR", "HER2", "KRAS", "MYC", "AKT", "PTEN"]
        for gene in gene_patterns:
            if gene in prompt:
                extracted_genes.append(gene)
        
        # Bridge cross-modal - use actual user query!
        if "bridge" in prompt_lower or "cross-modal" in prompt_lower or "generate" in prompt_lower:
            # Build queries using actual user text
            base_query = user_query or "protein function"
            
            queries = {
                "articles": f"{base_query} research literature",
                "experiments": f"{base_query} gene expression dataset",
                "proteins": f"{base_query} protein interaction",
                "images": f"{base_query} pathway diagram",
                "structures": f"{base_query} protein structure 3D",
            }
            
            # Use extracted genes or defaults based on query
            genes = extracted_genes[:5] if extracted_genes else []
            if not genes and user_query:
                # Check if user query looks like a gene name
                if user_query.isupper() and len(user_query) <= 10:
                    genes = [user_query]
            
            return json.dumps({
                "queries": queries,
                "filters": {
                    "genes": genes,
                    "diseases": [],
                    "pathways": [],
                },
                "alignment": "aligned",
                "interpretation": f"Search results for '{base_query}'. Identified entities related to the query."
            })
        
        # Design candidates
        if "design" in prompt_lower or "candidate" in prompt_lower:
            return json.dumps({
                "candidates": [
                    {
                        "name": "Related Protein 1",
                        "justification": "Potential functional relationship",
                        "research_suggestion": "Investigate interaction"
                    },
                    {
                        "name": "Related Protein 2", 
                        "justification": "Shared pathway involvement",
                        "research_suggestion": "Study co-expression"
                    },
                    {
                        "name": "Related Protein 3",
                        "justification": "Structural similarity",
                        "research_suggestion": "Evaluate as target"
                    }
                ],
                "summary": f"Analysis based on search results for {user_query or 'query'}."
            })
        
        # Summary
        if "summary" in prompt_lower or "summarize" in prompt_lower:
            return f"Search results identified entities related to {user_query or 'the query'}."
        
        return json.dumps({"response": "Mock response generated"})
    
    # =========================================================================
    # BRIDGE CROSS-MODAL (Architecture v3.0)
    # =========================================================================
    
    async def bridge_cross_modal(
        self,
        user_text: Optional[str],
        modality_metadata: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Bridge LLM: Generate queries and filters from modality metadata
        
        INPUT:
        - user_text: User's text query (None for CAS 2)
        - modality_metadata: Metadata from Phase 1 results
        
        OUTPUT:
        {
            "queries": {collection: query_string},
            "filters": {"genes": [], "diseases": [], "pathways": []},
            "alignment": "aligned" | "partial" | "divergent",
            "interpretation": "Summary text..."
        }
        """
        # Format metadata for prompt
        metadata_str = ""
        for i, item in enumerate(modality_metadata[:5]):
            name = item.get("name", "Unknown")
            score = item.get("score", 0)
            genes = item.get("genes", [])
            diseases = item.get("diseases", [])
            func = item.get("function", item.get("abstract", item.get("description", "")))
            
            metadata_str += f"{i+1}. {name} (score: {score:.3f})\n"
            if genes:
                metadata_str += f"   Genes: {', '.join(genes[:5])}\n"
            if diseases:
                metadata_str += f"   Diseases: {', '.join(diseases[:3])}\n"
            if func:
                metadata_str += f"   Info: {func[:150]}...\n"
        
        # Build prompt
        prompt = f"""You are a biomedical search assistant. Analyze the search results and generate optimized cross-modal queries.

{"USER QUERY: " + user_text if user_text else "NO USER TEXT (modal-only search)"}

PHASE 1 RESULTS (from modality search):
{metadata_str if metadata_str else "No results available"}

Generate a JSON response with:

1. "queries": Object with optimized search queries for each collection:
   - "articles": query for scientific literature (focus on key concepts)
   - "experiments": query for experimental datasets (GEO, ArrayExpress)
   - "proteins": query for protein databases (function, interactions)
   - "images": query for pathway/cellular images
   - "structures": query for protein structures (PDB)

2. "filters": Object with biological entities to filter by:
   - "genes": list of gene names (max 5, from results or inferred)
   - "diseases": list of diseases (max 3)
   - "pathways": list of biological pathways (max 3)

3. "alignment": Assess if user text and modality results are about the same topic:
   - "aligned": Same biological topic/context
   - "partial": Related but different aspects
   - "divergent": Unrelated topics (user should be warned)

4. "interpretation": 2-3 sentence summary explaining what was found and the biological relevance.

Return ONLY valid JSON, no markdown or other text."""

        response = await self.generate(prompt)
        
        try:
            # Clean response
            response = response.strip()
            if response.startswith("```"):
                response = re.sub(r'^```\w*\n?', '', response)
                response = re.sub(r'\n?```$', '', response)
            
            result = json.loads(response)
            
            # Validate and return
            return {
                "queries": result.get("queries", {}),
                "filters": result.get("filters", {"genes": [], "diseases": [], "pathways": []}),
                "alignment": result.get("alignment", "aligned"),
                "interpretation": result.get("interpretation", "Results found for the given modality."),
            }
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Bridge response: {e}")
            logger.warning(f"Response was: {response[:200]}")
            
            # Extract genes from metadata as fallback
            fallback_genes = []
            for item in modality_metadata:
                fallback_genes.extend(item.get("genes", []))
            fallback_genes = list(set(fallback_genes))[:5]
            
            return {
                "queries": {
                    "articles": user_text or "protein function",
                    "experiments": user_text or "gene expression",
                    "proteins": user_text or "protein structure",
                    "images": user_text or "pathway diagram",
                    "structures": user_text or "protein 3D structure",
                },
                "filters": {"genes": fallback_genes, "diseases": [], "pathways": []},
                "alignment": "aligned",
                "interpretation": "Search results found.",
            }
    
    # =========================================================================
    # DESIGN ASSISTANT
    # =========================================================================
    
    async def generate_design_candidates(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """Generate design candidates with justifications"""
        results_text = ""
        for i, r in enumerate(results[:10]):
            name = r.get("name") or r.get("payload", {}).get("protein_name") or r.get("payload", {}).get("title", "Unknown")
            score = r.get("score", 0)
            coll = r.get("collection", "unknown")
            results_text += f"{i+1}. [{coll}] {name} (score: {score:.3f})\n"
        
        prompt = f"""As a biological research assistant, analyze these search results and suggest research directions.

QUERY: {query}

RESULTS:
{results_text}

Generate a JSON response with:
- candidates: list of {top_k} objects, each with:
  - name: entity name (from results)
  - justification: why this is scientifically relevant (1-2 sentences)
  - research_suggestion: potential research direction (1 sentence)
- summary: overall finding summary (2-3 sentences)

Focus on novel connections and research opportunities.
Return ONLY valid JSON."""

        response = await self.generate(prompt)
        
        try:
            response = response.strip()
            if response.startswith("```"):
                response = re.sub(r'^```\w*\n?', '', response)
                response = re.sub(r'\n?```$', '', response)
            
            result = json.loads(response)
            return {
                "candidates": result.get("candidates", []),
                "summary": result.get("summary", ""),
            }
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse Design response")
            return {
                "candidates": [],
                "summary": "Results analyzed.",
            }
    
    # =========================================================================
    # SUMMARY GENERATION
    # =========================================================================
    
    async def generate_summary(
        self,
        query: str,
        results: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """Generate summary of search results"""
        overview_parts = []
        for collection, items in results.items():
            if items:
                names = []
                for item in items[:3]:
                    payload = item.get("payload", {})
                    name = payload.get("protein_name") or payload.get("title") or payload.get("caption", "Unknown")
                    if isinstance(name, str):
                        names.append(name[:30])
                if names:
                    overview_parts.append(f"{collection}: {', '.join(names)}")
        
        results_overview = "\n".join(overview_parts)
        
        prompt = f"""Summarize these biological search results in 2-3 sentences.

QUERY: {query}

RESULTS OVERVIEW:
{results_overview}

Focus on main findings and biological connections.
Return ONLY the summary text, no JSON."""

        response = await self.generate(prompt)
        
        response = response.strip()
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]
        
        return response


# Singleton accessor
def get_llm() -> GeminiClient:
    return GeminiClient()