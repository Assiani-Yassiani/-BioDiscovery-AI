"""
Robots Module - Collecte automatique de données biomédicales
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from .robot_papers import RobotPapers
from .robot_sequences import RobotSequences
from .robot_experiments import RobotExperiments
from .robot_images import RobotImages
from .robot_structures import RobotStructures

__all__ = ["RobotPapers", "RobotSequences", "RobotExperiments", "RobotImages", "RobotStructures"]

