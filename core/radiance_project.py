from dataclasses import dataclass
from typing import Dict, Optional, List
from pathlib import Path

@dataclass
class ProjectConfig:
    
    # --- Configuration settings for pyRadiance rendering project ---
    
    name: str
    descirption: str = ""
    
    latitude: float = 37.79
    longitude: float = -122.41
    timezone: str = "America/Los_Angeles"
    
    default_resolution: tuple[int, int] = (1000, 1000)
    default_quality: str = "medium"
    
    create_dated_subdirs: bool = True
    keep_intermediate_files: bool = False
    
    max_parallel_renders: int = 4
    cache_octrees: bool = True
    
    def to_dict(self) -> Dict:
        
        # --- Converts from dataclass to dictionary for JSON serialization ---
        
        return {
            'name': self.name,
            'description': self.description,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'timezone': self.timezone,
            'default_resolution': list(self.default_resolution),
            'default_quality': self.default_quality,
            'create_dated_subdirs': self.create_dated_subdirs,
            'keep_intermediate_files': self.keep_intermediate_files,
            'max_parallel_renders': self.max_parallel_renders,
            'cache_octrees': self.cache_octrees,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProjectConfig':
        
        # --- Converts from dictionary to dataclass for JSON deserialization ---
        
        if 'default_resolution' in data:
            data['default_resolution'] = tuple(data['default_resolution'])
        return cls(**data)
    
class RadianceProject:
    
    def __init__(self, project_dir: Path | str, config: Optional[ProjectConfig] = None, create_if_missing: bool = True):
        
        self.root = Path(project_dir).resolve()
        self.config = config or ProjectConfig(name=self.root.name)
        
        self.dirs = {
            'scenes': self.root / 'scenes',
            'materials': self.root / 'materials',
            'views': self.root / 'views',
            'octrees': self.root / 'octrees',
            'renders': self.root / 'renders',
            'temp': self.root / 'temp',
            'logs': self.root / 'logs',
        }
        
        if create_if_missing:
            self._create_structure()
        
        # --- List of temporary resources we create during rendering, for clean-up ---
        self._temp_resource: List[Path] = []
        # --- List of cached data for quick access (Dict is 0(1)) ---
        self._cache: Dict[str, any] = {}
            
    def _create_structure(self):
        
        self.root.mkdir(parents=True, exist_ok=True)
        for dir_path in self.dirs.values():
            dir_path.mkdir(exist_ok=True)
            
        config_file = self.root / 'config.json'
        if not config_file.exists():
            self.save_config()
            
    def save_config(self, path: Optional[Path] = None) -> None: 
        
        config_path = path or (self.root / 'config.json')
        
        with open(config_path, 'w') as f:
            import json
            json.dump(self.config.to_dict(), f, indent=2)
            