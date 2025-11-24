import pyradiance as pr
from pathlib import Path
from typing import List, Union, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from .radiance_project import RadianceProject

class SceneBuilder:
    """
    Manages the compilation of Radiance scenes using the two-octree pattern.
    
    This class handles:
    1. Building a base octree (geometry + materials) - slow, done once
    2. Building sky octrees (base + sky) - fast, done per frame
    """
    
    def __init__(self, project: 'RadianceProject', scene_id: str = "scene"):
        """
        Initialize the SceneBuilder.
        
        Args:
            project: RadianceProject object containing configuration and directory structure
            scene_id: Optional identifier for this scene (default: "scene")
        """
        self.project = project
        self.scene_id = scene_id
        self.output_dir = project.dirs['octrees']
        self.geometry_files: List[Path] = []
        self.material_files: List[Path] = []
        
        # Ensure output directory exists (should already exist from project)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def add_geometry(self, *files: Union[str, Path]):
        """Add geometry (.rad) files to the scene."""
        for f in files:
            self.geometry_files.append(Path(f))

    def add_materials(self, *files: Union[str, Path]):
        """Add material (.mat or .rad) files to the scene."""
        for f in files:
            self.material_files.append(Path(f))

    def convert_obj_to_rad(self, obj_path: Union[str, Path], add_to_scene: bool = True) -> tuple[str, str]:
        """
        Convert an OBJ file to RAD and MAT files if they don't already exist.
        
        Args:
            obj_path: Path to the OBJ file to convert
            add_to_scene: If True, automatically add the generated files to this scene (default: True)
            
        Returns:
            Tuple of (rad_file_path, mat_file_path)
            
        Note:
            This function will skip conversion if both .rad and .mat files already exist,
            making it safe to call repeatedly in scripts without regenerating files.
        """
        # --- basic error protection ---
        obj_path = Path(obj_path).resolve()
        if not obj_path.exists():
            raise FileNotFoundError(f"OBJ file not found: {obj_path}")
        
        # --- create file names ---
        base = obj_path.with_suffix("")
        rad_file = str(base) + ".rad"
        mat_file = str(base) + ".mat"
        
        # Check if files already exist
        if Path(rad_file).exists() and Path(mat_file).exists():
            print(f"✓ RAD files already exist for {obj_path.name}, skipping conversion")
        else:
            print(f"Converting {obj_path.name} to RAD format...")
            
            # Convert OBJ to RAD
            rad_bytes = pr.obj2rad(str(obj_path))
            Path(rad_file).write_bytes(rad_bytes)

            # --- get group names ---
            groups = []
            seen = set()
            with obj_path.open("r", errors="ignore") as f:
                for line in f:
                    if line.strip().startswith("g "):
                        name = line.strip().split(maxsplit=1)[1]
                        if name not in seen:
                            seen.add(name)
                            groups.append(name)

            # --- sanitize names for radiance ---
            def sanitize(name: str) -> str:
                return re.sub(r"[^A-Za-z0-9_.-]", "_", name)

            # --- write mat file ---
            with open(mat_file, "w", encoding="utf-8") as f:
                if not groups:
                    f.write("void plastic default_layer\n0\n0\n5 0.5 0.5 0.5 0 0\n")
                else:
                    for g in groups:
                        safe_name = sanitize(g)
                        f.write(f"void plastic {safe_name}\n0\n0\n5 0.5 0.5 0.5 0 0\n\n")
            
            print(f"✓ Created {Path(rad_file).name} and {Path(mat_file).name}")
        
        # Optionally add to scene
        if add_to_scene:
            self.add_geometry(rad_file)
            self.add_materials(mat_file)
            print(f"✓ Added files to scene")
        
        return rad_file, mat_file

    def build_base_octree(self) -> Path:
        """
        Builds the base octree containing static geometry and materials.
        
        Returns:
            Path to the compiled octree file
        """
        output_path = self.output_dir / f"{self.scene_id}_base.oct"
        
        # Convert paths to strings for pyradiance
        surf_files = [str(f) for f in self.geometry_files]
        mat_files = [str(f) for f in self.material_files]
        
        print(f"Building base octree: {output_path}...")
        
        try:
            # Combine all inputs
            all_inputs = mat_files + surf_files
            
            octree_bytes = pr.oconv(*all_inputs)
            
            with open(output_path, "wb") as f:
                f.write(octree_bytes)
                
            print(f"✓ Base octree created: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error building base octree: {e}")
            raise

    def build_sky_octree(self, 
                        base_octree: Union[str, Path], 
                        sky_definition: bytes, 
                        output_name: str, 
                        sky_rotation: float = 0.0) -> Path:
        """
        Builds a sky octree by combining the base octree with a sky definition.
        
        Args:
            base_octree: Path to the base octree (from build_base_octree)
            sky_definition: Bytes containing the sky description (from gensky)
            output_name: Name for the output file (without extension)
            sky_rotation: Rotation in degrees for the sky (default: 0.0)
            
        Returns:
            Path to the compiled sky octree
        """
        output_path = self.output_dir / f"{output_name}.oct"
        
        try:
            # Handle rotation if needed
            if sky_rotation != 0.0:
                xform = pr.Xform(inp=sky_definition)
                xform.rotatez(deg=sky_rotation)
                final_sky = xform()
            else:
                final_sky = sky_definition

            # Combine sky with base octree using oconv
            octree_bytes = pr.oconv(
                stdin=final_sky,
                octree=str(base_octree),
                warning=True
            )
            
            with open(output_path, "wb") as f:
                f.write(octree_bytes)
                
            return output_path
            
        except Exception as e:
            print(f"Error building sky octree {output_name}: {e}")
            raise