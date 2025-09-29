# app.py
# LeafLens - Final Version with Simultaneous Spraying

import streamlit as st
import numpy as np
import time
import random
from datetime import datetime
import base64
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from streamlit_clickable_images import clickable_images

# --- Page Configuration ---
st.set_page_config(
    page_title="LeafLens", # CHANGED: Title updated to LeafLens
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Constants & State Mapping ---
GRID_ROWS = 4
GRID_COLS = 4
STATE_HEALTHY = 0
STATE_DISEASED = 1
STATE_SPRAYING = 2
STATE_SCANNING = 3
STATE_SPRAYED = 4
IMAGE_PATH = "crop_top_view.png"

# --- FONT CONSTANT: MUST MATCH THE FILE ON GITHUB ---
FONT_PATH = "Roboto-Regular.ttf"

# --- VIDEO CONSTANT UPDATED TO LOCAL FILE REFERENCE ---
# FIX: Using the local file name. Ensure 'Camera feed.mp4' is on GitHub!
CAMERA_FEED_URL = "Camera feed.mp4" 

# --- Helper Functions ---

# FIX: Removed @st.cache_data to prevent object serialization errors for image object
def get_base_image(path):
    try: return Image.open(path).convert("RGBA")
    except FileNotFoundError: st.error(f"Image file not found at '{path}'."); return None

# FIX: Removed @st.cache_data and uses truetype with the file to respect size
def get_font(size):
    try:
        # Use the uploaded font file to ensure size is respected
        return ImageFont.truetype(FONT_PATH, size)
    except IOError:
        # Fall back to default if font file is missing
        return ImageFont.load_default()

def create_grid_image(base_img, status, text):
    if base_img is None: return None
    tile = base_img.copy()
    overlay = Image.new("RGBA", tile.size)
    draw = ImageDraw.Draw(overlay)
    status_map = {
        STATE_HEALTHY: {"color": (46, 204, 113, 100), "label": "Healthy"},
        STATE_DISEASED: {"color": (231, 76, 60, 150), "label": "Diseased"},
        STATE_SPRAYING: {"color": (52, 152, 219, 150), "label": "Spraying"},
        STATE_SCANNING: {"color": (241, 196, 15, 150), "label": "Scanning"},
        STATE_SPRAYED: {"color": (142, 68, 173, 150), "label": "Sprayed"},
    }
    config = status_map.get(status, {"color": (0,0,0,80), "label": "Unknown"})
    draw.rectangle([(0, 0), tile.size], fill=config["color"])
    tile = Image.alpha_composite(tile, overlay)
    draw = ImageDraw.Draw(tile)
    
    # FONT SIZE IS SET TO 35
    font = get_font(35) 
    
    full_text = f"{text}\n({config['label']})"
    text_bbox = draw.textbbox((0, 0), full_text, font=font)
    text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
    text_pos = ((tile.width - text_width) / 2, (tile.height - text_height) / 2)
    draw.text((text_pos[0]+1, text_pos[1]+1), full_text, font=font, fill="black")
    draw.text(text_pos, full_text, font=font, fill="white")
    buffered = BytesIO()
    tile.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def add_to_log(message):
    st.session_state.event_log.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.event_log) > 20: st.session_state.event_log.pop()

# --- State Initialization ---
if 'initialized' not in st.session_state:
    st.session_state.grid_status = np.full((GRID_ROWS, GRID_COLS), STATE_HEALTHY, dtype=int)
    st.session_state.tank_level = 100.0
    st.session_state.battery_level = 100.0
    st.session_state.sprayed_plots_count = 0
    st.session_state.event_log = []
    st.session_state.system_status = "Idle"
    st.session_state.view = "dashboard"
    st.session_state.initialized = True
    add_to_log("System Initialized. Ready for operation.")

# --- UI Styling (Updated Gradient and Title Container) ---
st.markdown("""
<style>
    .title-gradient {
        font-size: 3.5rem;
        font-weight: bold;
        /* FIX: Changed gradient to visible Blue-Green transition */
        background: -webkit-linear-gradient(45deg, #2193b0, #2ecc71); 
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline-block; 
    }
    /* FIX: Container to hold the emoji and the gradient text side-by-side */
    .title-container {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .title-container h1 {
        margin: 0;
        padding: 0;
        font-size: 3.5rem;
    }
</style>
""", unsafe_allow_html=True)


# --- Sidebar Controls ---
is_running = st.session_state.system_status != "Idle"
with st.sidebar:
    st.header("⚙️ System Controls")
    st.divider()
    st.subheader("Autonomous Mode")
    if st.button("▶️ Start Autonomous Cycle", use_container_width=True, type="primary", disabled=is_running):
        st.session_state.view = "autonomous_cycle"
        st.rerun()

    st.divider()
    st.subheader("Manual Spray")
    row_sel = st.selectbox("Select Row", range(GRID_ROWS), disabled=is_running)
    col_sel = st.selectbox("Select Column", range(GRID_COLS), disabled=is_running)
    manual_amount = st.slider("Pesticide Amount (%)", 1.0, 10.0, 2.5, 0.5, disabled=is_running)

    if st.button("Spray Selected Grid", use_container_width=True, disabled=is_running):
        st.session_state.view = "manual_spray"
        st.session_state.manual_target = {"coords": (row_sel, col_sel), "amount": manual_amount}
        st.rerun()
    
    if st.button("🚨 Spray Entire Field", use_container_width=True, disabled=is_running):
        st.session_state.view = "blanket_spray"
        st.rerun()
        
# --- Main View Controller ---

## --- Dashboard Components ---
# Render title, metrics, and set up containers regardless of dashboard state
st.markdown('<div class="title-container"><h1>🌱</h1><div class="title-gradient">LeafLens</div></div>', unsafe_allow_html=True)
st.markdown("See. Detect. Protect.") 
st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1: st.metric(label="System Status", value=st.session_state.system_status)
with col2: st.metric(label="Grids Treated", value=st.session_state.sprayed_plots_count)
with col3: st.metric(label="Tank Level", value=f"{st.session_state.tank_level:.1f} %")
with col4: st.metric(label="Cameras Active", value="4") 

st.divider()

# --- TOP ROW SETUP: Map and Video Containers ---
# Map (3.5) and Video (1.5)
map_col, video_col = st.columns([3.5, 1.5])

# --- Placeholder definitions for animation ---
# These need to be defined outside the if/else to be used by the animation logic.
# They are scoped to the columns defined above.
with map_col:
    map_header_placeholder = st.empty()
    grid_placeholder = st.empty()

with video_col:
    video_header_placeholder = st.empty()
    video_player_placeholder = st.empty()
    
# Progress bar placeholder (used during animation)
progress_placeholder = st.empty() 

# --- Update function shared by dashboard and animation ---
def update_static_display(status_array, is_dashboard_view=False):
    base_image = get_base_image(IMAGE_PATH)
    if not base_image: return
    
    # Render the static map header or just clear it if animating
    map_header_placeholder.subheader("1 Acre - 4x4 Grids")
    
    # Render the actual grid visuals into the placeholder
    with grid_placeholder.container():
        if is_dashboard_view:
            # Use clickable images for the dashboard view
            images_b64 = [f"data:image/png;base64,{create_grid_image(base_image, st.session_state.grid_status[r,c], f'Grid ({r},{c})')}" for r in range(GRID_ROWS) for c in range(GRID_COLS)]
            clicked_index = clickable_images(images_b64, titles=[f"Grid {i}" for i in range(len(images_b64))], div_style={"display": "grid", "grid-template-columns": f"repeat({GRID_COLS}, 1fr)", "gap": "8px"}, img_style={"height": "130px", "width": "100%", "object-fit": "cover", "border-radius": "10px", "cursor": "pointer"})
            
            # Handle manual disease marking click event
            if clicked_index > -1:
                r, c = clicked_index // GRID_COLS, clicked_index % GRID_COLS
                if st.session_state.grid_status[r, c] in [STATE_HEALTHY, STATE_SPRAYED]:
                    st.session_state.grid_status[r, c] = STATE_DISEASED
                    add_to_log(f"Manual Inspection: Disease marked at Grid ({r},{c}).")
                    st.rerun()
        else:
            # Use simple image rendering for animation view (non-clickable)
            cols = st.columns(GRID_COLS)
            for i in range(GRID_ROWS * GRID_COLS):
                r, c = i // GRID_COLS, i % GRID_COLS
                img_b64 = create_grid_image(base_image, status_array[r, c], f'Grid ({r},{c})')
                cols[c].image(f"data:image/png;base64,{img_b64}")

# --- Video/Log update utility ---
def update_video_and_log():
    # Video
    video_header_placeholder.subheader("📹 Live Feed")
    
    # FIX: Use HTML Markdown injection to remove controls and simulate GIF behavior
    html_video = f"""
    <video width="100%" height="auto" autoplay loop muted playsinline>
        <source src="{CAMERA_FEED_URL}" type="video/mp4">
        Your browser does not support the video tag.
    </video>
    """
    video_player_placeholder.markdown(html_video, unsafe_allow_html=True)


    # Log
    st.subheader("📜 Event Log")
    log_content = "<br>".join(st.session_state.event_log)
    st.markdown(f'<div style="background-color:#1F2937; border-radius:10px; padding:10px; height:200px; overflow-y:auto; border:1px solid #4B5563; font-family:monospace;">{log_content}</div>', unsafe_allow_html=True)


## --- VIEW LOGIC ---
if st.session_state.view == "dashboard":
    # RENDER DASHBOARD: Map is clickable, video and log are static.
    update_static_display(st.session_state.grid_status, is_dashboard_view=True)
    update_video_and_log()

else: # This handles 'autonomous_cycle', 'manual_spray', 'blanket_spray'
    # RENDER ANIMATION SETUP: Map is animated, video and log are static.
    update_video_and_log()
    
    # --- Logic for Autonomous Cycle (FIXED SCANNING FLOW) ---
    if st.session_state.view == "autonomous_cycle":
        st.session_state.system_status = "Scanning"
        add_to_log("🤖 Autonomous scan initiated on main grid...")
        
        num_diseased = random.randint(3, 5)
        all_coords = [(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)]
        diseased_coords = set(random.sample(all_coords, num_diseased)) 
        
        current_status = st.session_state.grid_status.copy()
        
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                # 1. SHOW SCANNING (Flash yellow)
                current_status[r, c] = STATE_SCANNING
                update_static_display(current_status) # Updates grid_placeholder in map_col
                time.sleep(0.15) 
                
                # 2. DETERMINE FINAL STATE & REVEAL
                is_diseased = (r, c) in diseased_coords
                
                if is_diseased:
                    final_state = STATE_DISEASED
                else:
                    final_state = STATE_HEALTHY 
                    
                st.session_state.grid_status[r, c] = final_state 
                current_status[r, c] = final_state
                
                update_static_display(current_status)
                time.sleep(0.05) 

        add_to_log(f"✅ Scan complete. Found {num_diseased} diseased plots.")
        st.session_state.system_status = "Spraying"
        add_to_log("💧 Initiating simultaneous targeted spraying..."); time.sleep(1)

        for r_plot, c_plot in diseased_coords:
            st.session_state.grid_status[r_plot, c_plot] = STATE_SPRAYING
        update_static_display(st.session_state.grid_status)
        
        bar = progress_placeholder.progress(0, text=f"Spraying {len(diseased_coords)} grids...")
        for i in range(100): time.sleep(0.1); bar.progress(i + 1)
        progress_placeholder.empty()

        for r_plot, c_plot in diseased_coords:
            st.session_state.grid_status[r_plot, c_plot] = STATE_SPRAYED
            st.session_state.sprayed_plots_count += 1
            st.session_state.tank_level = max(0, st.session_state.tank_level - 2.5)
        add_to_log(f"✅ {len(diseased_coords)} grids have been treated.")
        
        st.session_state.system_status = "Idle"
        st.session_state.view = "dashboard"
        st.rerun()

    # --- Logic for Manual Spray ---
    elif st.session_state.view == "manual_spray":
        st.session_state.system_status = "Spraying"
        target = st.session_state.manual_target
        r, c = target["coords"]; amount = target["amount"]
        add_to_log(f"🛠️ Manual spray for Grid ({r},{c}) with {amount}% pesticide.")
        st.session_state.grid_status[r, c] = STATE_SPRAYING
        update_static_display(st.session_state.grid_status)
        
        bar = progress_placeholder.progress(0, text=f"Spraying Grid ({r},{c})...")
        for i in range(100): time.sleep(0.1); bar.progress(i + 1)
        progress_placeholder.empty()

        st.session_state.grid_status[r, c] = STATE_SPRAYED
        st.session_state.tank_level = max(0, st.session_state.tank_level - amount)
        st.session_state.sprayed_plots_count += 1
        add_to_log(f"✅ Grid ({r},{c}) has been treated.")
        
        del st.session_state.manual_target
        st.session_state.system_status = "Idle"
        st.session_state.view = "dashboard"
        st.rerun()

    # --- Logic for Blanket Spray ---
    elif st.session_state.view == "blanket_spray":
        st.session_state.system_status = "Spraying"
        add_to_log("📢 Simultaneous blanket spray initiated for all grids.")
        
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                st.session_state.grid_status[r, c] = STATE_SPRAYING
        update_static_display(st.session_state.grid_status)

        bar = progress_placeholder.progress(0, text=f"Spraying all 16 grids...")
        for i in range(100): time.sleep(0.15); bar.progress(i + 1)
        progress_placeholder.empty()

        plots_actually_sprayed = 0
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                if st.session_state.tank_level > 0:
                    st.session_state.grid_status[r, c] = STATE_SPRAYED
                    st.session_state.tank_level = max(0, st.session_state.tank_level - 1.5)
                    st.session_state.sprayed_plots_count += 1
                    plots_actually_sprayed += 1
                else:
                    st.session_state.grid_status[r, c] = STATE_HEALTHY # Revert if no pesticide left
        
        if plots_actually_sprayed < GRID_ROWS * GRID_COLS:
            add_to_log(f"⚠️ Tank empty. Only {plots_actually_sprayed} grids were treated.")
        add_to_log("✅ Blanket spray complete.")
        st.session_state.system_status = "Idle"
        st.session_state.view = "dashboard"
        st.rerun()
