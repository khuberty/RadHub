from dataclasses import dataclass
from typing import Dict, Optional, List
from pathlib import Path
from contextlib import contextmanager

import os, shutil, tempfile, json, datetime


@dataclass
class ProjectConfig:
    
    # --- Configuration settings for pyRadiance rendering project ---
    
    name: str
    description: str = ""
    
    latitude: float = 37.79
    longitude: float = 122.41
    timezone: float = 120
    
    default_resolution: tuple[int, int] = (1000, 1000)
    default_quality: str = "Medium"
    
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
            
    @classmethod
    def load(cls, project_dir: Path | str) -> 'RadianceProject':
        
        root = Path(project_dir).resolve()
        config_path = root / 'config.json'
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"No config.json found in {root}. "
            )
            
        with open(config_path, 'r') as f:
            config_data = json.load(f)
            
        config = ProjectConfig.from_dict(config_data)
        return cls(root, config, create_if_missing=False)
      
    # --- Helper Scripts ---  
      
    def get_path(self, category: str, filename: str) -> Path:
        if category not in self.dirs:
            raise ValueError(
                f"Unknown category '{category}'. "
                f"Valid categories: {list(self.dirs.keys())}"
            )
        return self.dirs[category] / filename
    
    @contextmanager
    def temp_files(self, suffix: str = '', prefix: str = 'tmp') -> Path:
        fd, path = tempfile.mkstemp(
            suffix=suffix,
            prefix=prefix,
            dir=self.dirs['temp']
        )
        
        temp_path = Path(path)

        if not self.config.keep_intermediate_files:
            self._temp_resource.append(temp_path)
            
        try:
            yield temp_path
        finally:
            try:
                os.close(fd)
            except:
                pass
    
    def cleanup_temp_files(self) -> None:
        for resource in reversed(self._temp_resource):
            try:
                if resource.exists():
                    if resource.is_file():
                        resource.unlink()
                    elif resource.is_dir():
                        shutil.rmtree(resource)    
            except:
                print(f"This temp file no longer exists: {resource}")
            
        self._temp_resource.clear()
        
    def list_resources(self, category: str, pattern: str = "*") -> List[str]:
        if category not in self.dirs:
            raise ValueError(f"Category not found: {category}")
        
        return list(self.dirs[category].glob(pattern))\
            
    def create_dated_subdir(self, category: str) -> Path:
        
        if category not in self.dir:
            raise ValueError(f"Unknown category: {category}")
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        subdir = self.dirs[category] / date_str
        subdir.mkdir(exist_ok=True)
        
        return subdir
    
    