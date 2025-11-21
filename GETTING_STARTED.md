# Getting Started with RadHub

## Prerequisites

You need:
1. Python 3.8+ installed
2. pyradiance installed: `pip install pyradiance`
3. Radiance installed and in PATH
4. Basic Radiance knowledge (what .rad files are, etc.)

## Your First Project

Let's create a simple daylight study step by step.

### Step 1: Create Project Structure

```python
from radhub import RadianceProject

# Create a new project
project = RadianceProject("my_first_study")

# Set location (latitude, longitude)
project.set_location(34.05, -118.24)  # Los Angeles
```

This creates:
```
my_first_study/
├── config.json
├── geometry/
├── materials/
├── views/
├── octrees/
├── renders/
└── cache/
```

### Step 2: Add Your Geometry

Option A: Copy files into project
```python
project.add_geometry("path/to/building.rad", copy=True)
project.add_material("path/to/materials.mat", copy=True)
```

Option B: Just reference files (doesn't copy)
```python
project.add_geometry("path/to/building.rad", copy=False)
```

**What you need:**
- `.rad` files with your geometry (export from Rhino, Sketchup, etc.)
- `.mat` files with material definitions

### Step 3: Build Base Octree

```python
from radhub import SceneBuilder

# Create scene builder
builder = SceneBuilder(
    scene_id="building",
    output_dir=project.dirs['octrees']
)

# Add all your files
builder.add_geometry(*project.config['geometry_files'])
builder.add_materials(*project.config['material_files'])

# Compile to octree (this is the slow part)
base_octree = builder.build_base_octree()
```

This creates `building_base.oct` - your compiled geometry.

**Pro tip:** This only needs to run once unless geometry changes!

### Step 4: Generate Sky

```python
from radhub import SkyGenerator
from datetime import datetime

# Create sky generator for your location
sky_gen = SkyGenerator(
    latitude=project.config.latitude,
    longitude=project.config.longitude,
    timezone=project.config.timezone
)

# Generate sky for summer solstice at noon
sky_bytes = sky_gen.generate(
    time=datetime(2024, 6, 21, 12, 0),
    sky_type="clear"
)
```

**Sky types:**
- `"clear"` - Sunny, clear sky
- `"cloudy"` - Overcast, uniform
- `"intermediate"` - Partly cloudy
- `"uniform"` - Uniform brightness (testing)

### Step 5: Build Sky Octree

```python
# Combine base geometry + sky
sky_octree = builder.build_sky_octree(
    base_octree=base_octree,
    sky_definition=sky_bytes,
    output_name="summer_noon",
    sky_rotation=0.0  # Optional rotation
)
```

This creates `summer_noon.oct` - ready to render!

### Step 6: Create View File

Create `camera.vf` with your view parameters:

```
rvu -vf -vtv -vp 0 0 5 -vd 0 1 0 -vu 0 0 1 -vh 45 -vv 45
```

Or use Radiance commands to generate from your scene.

### Step 7: Render!

```python
from radhub import RenderPipeline, RenderQuality

# Create render pipeline with quality preset
pipeline = RenderPipeline(quality=RenderQuality.MEDIUM)

# Full render pipeline
output_path = pipeline.render_full_pipeline(
    octree_path=sky_octree,
    view="camera.vf",
    output_path=project.get_render_path("summer_noon", "ppm"),
    render_resolution=(2560, 1440),  # Render large (anti-aliasing)
    final_resolution=(1280, 720),     # Output smaller
    exposure_adjust=-1.1,             # Adjust in pfilt
    final_exposure=-1.0,              # Fine tune in ra_ppm
)

print(f"Render saved to: {output_path}")
```

**Quality levels:**
- `RenderQuality.PREVIEW` - Fast preview (~5 sec)
- `RenderQuality.MEDIUM` - Good quality (~30 sec)
- `RenderQuality.HIGH` - High quality (~2 min)
- `RenderQuality.PRODUCTION` - Best quality (~10+ min)

### Complete Script

Here's everything together:

```python
from radhub import (
    RadianceProject, 
    SceneBuilder, 
    SkyGenerator, 
    RenderPipeline, 
    RenderQuality
)
from datetime import datetime

# 1. Setup project
project = RadianceProject("daylight_study")
project.set_location(34.05, -118.24)
project.add_geometry("building.rad")
project.add_material("materials.mat")

# 2. Build base octree (slow, but only once!)
builder = SceneBuilder("scene", project.dirs['octrees'])
builder.add_geometry(*project.config['geometry_files'])
builder.add_materials(*project.config['material_files'])
base_octree = builder.build_base_octree()

# 3. Generate sky
sky_gen = SkyGenerator(34.05, -118.24)
sky = sky_gen.generate(datetime(2024, 6, 21, 12, 0), "clear")

# 4. Build sky octree (fast)
sky_octree = builder.build_sky_octree(base_octree, sky, "noon")

# 5. Render (medium speed)
pipeline = RenderPipeline(quality=RenderQuality.MEDIUM)
output = pipeline.render_full_pipeline(
    octree_path=sky_octree,
    view="camera.vf",
    output_path=project.get_render_path("noon", "ppm")
)

print(f"Done! Output: {output}")
```

## Animation (Time-lapse)

Want to render multiple times? Easy!

```python
# Build base octree once
base_octree = builder.build_base_octree()

# Render multiple times
from datetime import datetime

times = [
    datetime(2024, 6, 21, 8, 0),   # 8 AM
    datetime(2024, 6, 21, 12, 0),  # Noon
    datetime(2024, 6, 21, 16, 0),  # 4 PM
]

for i, time in enumerate(times):
    # Generate sky for this time
    sky = sky_gen.generate(time, "clear")
    
    # Build sky octree (fast because base is reused!)
    sky_oct = builder.build_sky_octree(
        base_octree, 
        sky, 
        f"frame_{i:04d}"
    )
    
    # Render
    output = pipeline.render_full_pipeline(
        octree_path=sky_oct,
        view="camera.vf",
        output_path=project.get_render_path(f"frame_{i:04d}", "ppm")
    )
    
    print(f"Frame {i}: {time.strftime('%H:%M')} → {output}")
```

**Key insight:** Base octree is reused! Only sky changes, so frames render fast.

## Time Series (Automatic)

For hourly/daily sequences:

```python
from datetime import datetime

start = datetime(2024, 6, 21, 6, 0)   # 6 AM
end = datetime(2024, 6, 21, 20, 0)    # 8 PM

frame_num = 0
for time, sky_bytes in sky_gen.generate_time_series(
    start_time=start,
    end_time=end,
    interval_hours=1.0,  # Every hour
    sky_type="clear"
):
    # Build and render
    sky_oct = builder.build_sky_octree(
        base_octree,
        sky_bytes, 
        f"frame_{frame_num:04d}"
    )
    
    output = pipeline.render_full_pipeline(
        octree_path=sky_oct,
        view="camera.vf",
        output_path=project.get_render_path(f"frame_{frame_num:04d}", "ppm")
    )
    
    frame_num += 1
    print(f"Frame {frame_num}: {time.strftime('%Y-%m-%d %H:%M')}")
```

## Common Adjustments

### Change Exposure

```python
# If renders are too bright/dark:
output = pipeline.render_full_pipeline(
    ...,
    exposure_adjust=-1.5,  # Darker (more negative = darker)
    final_exposure=-0.5,   # Lighter
)
```

**Rule of thumb:**
- Too bright? More negative exposure
- Too dark? More positive exposure

### Change Quality

```python
# For final presentations
pipeline = RenderPipeline(quality=RenderQuality.PRODUCTION)

# For quick tests
pipeline = RenderPipeline(quality=RenderQuality.PREVIEW)
```

### Custom Parameters

```python
# Override specific render parameters
pipeline = RenderPipeline(
    quality=RenderQuality.MEDIUM,
    custom_params={
        'ab': 2,  # More ambient bounces
        'aa': 0.15,  # Better accuracy
    }
)
```

### Multiple Views

```python
views = ["exterior.vf", "interior.vf", "aerial.vf"]

for view_name in views:
    view_path = Path(view_name)
    output = pipeline.render_full_pipeline(
        octree_path=sky_octree,
        view=view_path,
        output_path=project.get_render_path(
            f"noon_{view_path.stem}", 
            "ppm"
        )
    )
```

## Troubleshooting

### "File not found" errors

Make sure your .rad and .vf files exist:
```python
from pathlib import Path

rad_file = Path("building.rad")
if not rad_file.exists():
    print(f"Can't find: {rad_file}")
```

### Renders too slow?

Use `PREVIEW` quality for testing:
```python
pipeline = RenderPipeline(quality=RenderQuality.PREVIEW)
```

### Exposure wrong?

Adjust both exposure parameters:
```python
# Coarse adjustment (pfilt)
exposure_adjust=-1.0

# Fine tuning (ra_ppm)  
final_exposure=-0.5
```

### Build fails?

Check your .rad files are valid Radiance syntax:
```bash
xform -c building.rad  # Check syntax
```

### Want to see what's happening?

RadHub prints progress:
```
Creating new project: daylight_study
  ✓ Created geometry/
  ✓ Created materials/
...
Building base octree: scene...
  ✓ Base octree created: scene_base.oct
...
```

## Next Steps

1. **Learn the core components** - Read `README.md`
2. **Understand the architecture** - Read `ARCHITECTURE.md`
3. **See complete example** - Run `example_workflow.py`
4. **Add GUI** - Start with simple tkinter dialogs
5. **Extend functionality** - Create new classes using core API

## Getting Help

- Check docstrings: `help(RadianceProject)`
- Read source code: It's well-commented!
- Look at examples: `example_workflow.py`

## Tips for Success

1. **Build base octree once** - Then reuse for all times/conditions
2. **Use quality presets** - Don't tune parameters manually at first
3. **Start small** - Single render before animations
4. **Check intermediate files** - Look at .oct, .hdr files to debug
5. **Organize with projects** - Don't scatter files everywhere

Happy rendering! 🌞
