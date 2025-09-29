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
import pandas as pd # Import pandas for improved dataframe handling

# --- Page Configuration ---
st.set_page_config(
    page_title="LeafLens", 
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
CAMERA_FEED_URL = "Camera feed.mp4" 

# --- NEW DISEASE CONSTANT ---
DISEASE_TYPES = ["Blight (Severe)", "Rust (Moderate)", "Powdery Mildew (Moderate)", "Leaf Spot (Low)", "Aphids (Severe)", "Nematodes (Low)"]

# --- NEW CONSTANTS FOR CHEMICAL UNITS (Liters) ---
BASE_SPRAY_AMOUNT = 1.0 
TANK_CAPACITY_LITERS = 100.0 
# --- Note: AUTONOMOUS_SPRAY_AMOUNT is replaced by get_pesticide_amount ---


# --- Helper Functions ---

# FIX: Removed @st.cache_data to prevent object serialization errors for image object
def get_base_image(path):
    try: return Image.open(path).convert("RGBA")
    except FileNotFoundError: st.error(f"Image file not found at '{path}'. Please ensure it is uploaded to GitHub."); return None

# FIX: Removed @st.cache_data and uses truetype with the file to respect size
def get_font(size):
    try:
        # Use the uploaded font file to ensure size is respected
        return ImageFont.truetype(FONT_PATH, size)
    except IOError:
        # Fall back to default if font file is missing
        return ImageFont.load_default()

# UPDATED: Takes r, c index to display 1-based coordinates
def create_grid_image(base_img, status, r, c): 
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
    
    # FIX: Display 1-indexed coordinates (r+1, c+1)
    full_text = f"Grid ({r+1},{c+1})\n({config['label']})"
    
    text_bbox = draw.textbbox((0, 0), full_text, font=font)
    text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
    text_pos = ((tile.width - text_width) / 2, (tile.height - text_height) / 2)
    draw.text((text_pos[0]+1, text_pos[1]+1), full_text, font=font, fill="black")
    draw.text(text_pos, full_text, font=font, fill="white")
    buffered = BytesIO()
    tile.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# NEW: Function to encode the video file into a Base64 string for embedding
def get_video_base64(path):
    try:
        with open(path, "rb") as video_file:
            encoded_string = base64.b64encode(video_file.read()).decode()
        return encoded_string
    except FileNotFoundError:
        # If file is missing, log an error but don't crash the app
        st.error(f"Video file not found at '{path}'. Please ensure it is uploaded to GitHub.")
        return None

def add_to_log(message):
    st.session_state.event_log.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.event_log) > 20: st.session_state.event_log.pop()

# NEW: Function to determine urgency and set label
def get_urgency_level(disease_name):
    if "Severe" in disease_name:
        return "Severe 🔴"
    elif "Moderate" in disease_name:
        return "Moderate 🟠"
    else: # Low, or any other unknown disease
        return "Low 🟡"

# NEW: Function to calculate variable pesticide amount based on urgency
def get_pesticide_amount(disease_name):
    if "Severe" in disease_name:
        return 2.0 * BASE_SPRAY_AMOUNT # 2.0 L
    elif "Moderate" in disease_name:
        return 1.5 * BASE_SPRAY_AMOUNT # 1.5 L
    else: # Low or default
        return 1.0 * BASE_SPRAY_AMOUNT # 1.0 L

# --- State Initialization ---
if 'initialized' not in st.session_state:
    st.session_state.grid_status = np.full((GRID_ROWS, GRID_COLS), STATE_HEALTHY, dtype=int)
    st.session_state.tank_level = TANK_CAPACITY_LITERS # Changed to Liters
    st.session_state.battery_level = 100.0
    st.session_state.sprayed_plots_count = 0
    st.session_state.event_log = []
    st.session_state.system_status = "Idle"
    st.session_state.view = "dashboard"
    # NEW STATE: Stores results of the last scan
    st.session_state.last_scan_results = None 
    st.session_state.initialized = True
    add_to_log("System Initialized. Ready for operation.")

# --- UI Styling (Cleaned up CSS, Gradient/Title retained) ---
st.markdown("""
<style>
    .title-gradient {
        font-size: 3.5rem;
        font-weight: bold;
        background: -webkit-linear-gradient(45deg, #2193b0, #2ecc71); 
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline-block; 
    }
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
    st.subheader("Autonomous Cycle") 
    if st.button("▶️ Start Autonomous Cycle", use_container_width=True, type="primary", disabled=is_running):
        st.session_state.view = "autonomous_cycle"
        st.rerun()

    # NEW BUTTON ADDED HERE with Tooltip for disabled state
    scan_review_disabled = is_running or st.session_state.last_scan_results is None
    
    tooltip_message = "Complete Autonomous Scan first."
    
    # We use st.empty() to conditionally render the tooltip
    if scan_review_disabled:
        with st.empty():
             st.button("🔎 Review Last Scan", use_container_width=True, disabled=True, help=tooltip_message)
    else:
        if st.button("🔎 Review Last Scan", use_container_width=True, disabled=False):
            st.session_state.view = "review_scan"
            st.rerun()


    st.divider()
    st.subheader("Manual Spray")
    # FIX: Added index=0 and format_func for 1-based coordinates
    row_sel = st.selectbox("Select Row (1-4)", range(GRID_ROWS), index=0, format_func=lambda x: x + 1, disabled=is_running)
    # FIX: Added index=0 and format_func for 1-based coordinates
    col_sel = st.selectbox("Select Column (1-4)", range(GRID_COLS), index=0, format_func=lambda x: x + 1, disabled=is_running)
    # FIX: Slider unit changed to Liters (L)
    manual_amount = st.slider("Pesticide Amount (L)", 1.0, 10.0, 2.5, 0.5, disabled=is_running)

    if st.button("Spray Selected Grid", use_container_width=True, disabled=is_running):
        st.session_state.view = "manual_spray"
        # Store 0-indexed coordinates for array access (r, c), but use 1-indexed in UI
        st.session_state.manual_target = {"coords": (row_sel, col_sel), "amount": manual_amount}
        st.rerun()
    
    if st.button("🚨 Spray Entire Field", use_container_width=True, disabled=is_running):
        st.session_state.view = "blanket_spray"
        st.rerun()
        
# --- Main View Controller ---

## --- Dashboard Components ---
st.markdown('<div class="title-container"><h1>🌱</h1><div class="title-gradient">LeafLens</div></div>', unsafe_allow_html=True)
st.markdown("See. Detect. Protect.") 
st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1: st.metric(label="System Status", value=st.session_state.system_status)
with col2: st.metric(label="Grids Treated", value=st.session_state.sprayed_plots_count)
# FIX: Changed Tank Level unit to Liters (L)
with col3: st.metric(label="Tank Level", value=f"{st.session_state.tank_level:.1f} L") 
with col4: st.metric(label="Cameras Active", value="4") 

st.divider()

# --- TOP ROW SETUP: Map and Video Containers ---
map_col, video_col = st.columns([3.5, 1.5])

# --- Placeholder definitions for animation ---
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
    
    map_header_placeholder.subheader("1 Acre - 4x4 Grids")
    
    with grid_placeholder.container():
        if is_dashboard_view:
            # FIX: Correctly pass r and c indices to create_grid_image
            images_b64 = [f"data:image/png;base64,{create_grid_image(base_image, st.session_state.grid_status[r,c], r, c)}" for r in range(GRID_ROWS) for c in range(GRID_COLS)]
            
            # FIX: Increased image height to 180px for better vertical alignment
            clicked_index = clickable_images(images_b64, titles=[f"Grid {i}" for i in range(len(images_b64))], div_style={"display": "grid", "grid-template-columns": f"repeat({GRID_COLS}, 1fr)", "gap": "8px"}, img_style={"height": "180px", "width": "100%", "object-fit": "cover", "border-radius": "10px", "cursor": "pointer"})
            
            if clicked_index > -1:
                r, c = clicked_index // GRID_COLS, clicked_index % GRID_COLS
                if st.session_state.grid_status[r, c] in [STATE_HEALTHY, STATE_SPRAYED]:
                    st.session_state.grid_status[r, c] = STATE_DISEASED
                    # FIX: Log message uses 1-indexed coordinates
                    add_to_log(f"Manual Inspection: Disease marked at Grid ({r+1},{c+1}).")
                    st.rerun()
        else:
            cols = st.columns(GRID_COLS)
            for i in range(GRID_ROWS * GRID_COLS):
                r, c = i // GRID_COLS, i % GRID_COLS
                # FIX: Correctly pass r and c indices to create_grid_image
                img_b64 = create_grid_image(base_image, status_array[r, c], r, c)
                # Note: In the animation view, st.image scales, but the overall height should now be consistent 
                cols[c].image(f"data:image/png;base64,{img_b64}")

# --- Video/Log update utility ---
def update_video_and_log():
    # Video
    video_header_placeholder.subheader("📹 Live Feed")
    
    video_base64 = get_video_base64(CAMERA_FEED_URL)

    if video_base64:
        # Uses Base64 embedding to ensure autoplay, loop, mute, and NO controls
        html_video = f"""
        <video width="100%" height="auto" autoplay loop muted playspinslane>
            <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
            Your browser does not support the video tag.
        </video>
        """
        video_player_placeholder.markdown(html_video, unsafe_allow_html=True)
    # else: If video fails to load, the error message is displayed by get_video_base64()


    # Log
    st.subheader("📜 Event Log")
    log_content = "<br>".join(st.session_state.event_log)
    st.markdown(f'<div style="background-color:#1F2937; border-radius:10px; padding:10px; height:200px; overflow-y:auto; border:1px solid #4B5563; font-family:monospace;">{log_content}</div>', unsafe_allow_html=True)


## --- VIEW LOGIC ---
if st.session_state.view == "dashboard":
    update_static_display(st.session_state.grid_status, is_dashboard_view=True)
    update_video_and_log()

# --- NEW REVIEW SCAN VIEW ---
elif st.session_state.view == "review_scan":
    st.markdown('<div class="title-container"><h1>🌱</h1><div class="title-gradient">LeafLens</div></div>', unsafe_allow_html=True)
    st.markdown(f"**Current Task:** Reviewing Last Scan Results")
    st.divider()

    st.subheader("Last Autonomous Scan Findings")

    if st.session_state.last_scan_results and len(st.session_state.last_scan_results) > 0:
        
        # Prepare data for display
        results_data = [{
            # Coordinates are already stored as 1-indexed (r+1, c+1)
            "Grid Coords": f"({r['coords'][0]}, {r['coords'][1]})", 
            "Detected Disease": r['disease'].split(" (")[0], # Show only the name
            "Urgency": get_urgency_level(r['disease']), # Urgency level
            # FIX: Displaying the variable amount in Liters (L)
            "Pesticide Used": f"{r['pesticide_used']:.1f} L" 
        } for r in st.session_state.last_scan_results]
        
        st.success(f"Scan found **{len(results_data)}** plots requiring attention.")
        
        # Use Pandas DataFrame for better table display with colors
        df = pd.DataFrame(results_data)

        st.dataframe(df, hide_index=True, use_container_width=True)

    else:
        st.warning("No disease was detected in the last scan, or no scan data is available. Please run an Autonomous Cycle first.")

    st.divider()
    if st.button("← Back to Dashboard", type="primary"):
        st.session_state.view = "dashboard"
        st.rerun()

else: 
    update_video_and_log()
    
    # --- Logic for Autonomous Cycle (INSTANT SCANNING) ---
    if st.session_state.view == "autonomous_cycle":
        st.session_state.system_status = "Scanning"
        add_to_log("🤖 Autonomous scan initiated on main grid...")
        
        num_diseased = random.randint(3, 5)
        all_coords = [(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)]
        diseased_coords = set(random.sample(all_coords, num_diseased)) 
        
        current_status = st.session_state.grid_status.copy()
        scan_results_to_store = [] # Temporarily store results during scan

        # Step 1: Simulate Instant Scanning (Show all yellow quickly)
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                current_status[r, c] = STATE_SCANNING
        update_static_display(current_status) 
        time.sleep(0.5) # Wait half a second for the "scan flash"
        
        # Step 2: Determine and Apply Final States (Instantly)
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                is_diseased = (r, c) in diseased_coords
                
                if is_diseased:
                    final_state = STATE_DISEASED
                    detected_disease = random.choice(DISEASE_TYPES)
                    pesticide_used = get_pesticide_amount(detected_disease) # NEW: Calculate variable amount
                    
                    scan_results_to_store.append({
                        "coords": (r+1, c+1), # Store 1-indexed coordinates
                        "disease": detected_disease,
                        "pesticide_used": pesticide_used # Store variable amount
                    })
                else:
                    final_state = STATE_HEALTHY 
                    
                st.session_state.grid_status[r, c] = final_state 
                current_status[r, c] = final_state
        
        # Update the grid to final results instantly
        update_static_display(current_status) 
        time.sleep(0.5) # Wait half a second after results appear before moving to spraying

        # STORE FINAL SCAN RESULTS
        st.session_state.last_scan_results = scan_results_to_store
        
        add_to_log(f"✅ Scan complete. Found {len(st.session_state.last_scan_results)} diseased plots.")
        st.session_state.system_status = "Spraying"
        add_to_log("💧 Initiating simultaneous targeted spraying..."); time.sleep(1)

        # --- Spraying logic updated to use variable amounts ---
        total_sprayed_amount = 0
        
        for result in st.session_state.last_scan_results:
            r, c = result['coords'][0] - 1, result['coords'][1] - 1 # Convert back to 0-index for array access
            amount = result['pesticide_used']

            if st.session_state.tank_level >= amount:
                st.session_state.grid_status[r, c] = STATE_SPRAYING
                total_sprayed_amount += amount
            # If tank runs out, grids remain marked as DISEASED until manually sprayed/fixed
        
        update_static_display(st.session_state.grid_status)
        
        bar = progress_placeholder.progress(0, text=f"Spraying {len(diseased_coords)} grids...")
        for i in range(100): time.sleep(0.1); bar.progress(i + 1)
        progress_placeholder.empty()

        for result in st.session_state.last_scan_results:
            r, c = result['coords'][0] - 1, result['coords'][1] - 1
            amount = result['pesticide_used']
            
            if st.session_state.tank_level >= amount:
                st.session_state.grid_status[r, c] = STATE_SPRAYED
                st.session_state.sprayed_plots_count += 1
                st.session_state.tank_level -= amount
            else:
                 # If tank ran out, log failure to treat plot
                add_to_log(f"⚠️ Failed to spray Grid ({r+1},{c+1}). Tank empty.")

        add_to_log(f"✅ {len(diseased_coords)} grids have been treated. Used {total_sprayed_amount:.1f} L.")
        
        st.session_state.system_status = "Idle"
        st.session_state.view = "dashboard"
        st.rerun()

    # --- Logic for Manual Spray ---
    elif st.session_state.view == "manual_spray":
        st.session_state.system_status = "Spraying"
        target = st.session_state.manual_target
        # target["coords"] is already 0-indexed from selectbox
        r, c = target["coords"][0], target["coords"][1] 
        amount = target["amount"] # Amount is in Liters (L)
        
        add_to_log(f"🛠️ Manual spray for Grid ({r+1},{c+1}) with {amount:.1f} L pesticide.")

        if st.session_state.tank_level < amount:
            add_to_log(f"⚠️ Manual spray failed. Insufficient pesticide ({amount:.1f} L required, {st.session_state.tank_level:.1f} L available).")
            st.session_state.system_status = "Idle"
            st.session_state.view = "dashboard"
            st.rerun()
        
        st.session_state.grid_status[r, c] = STATE_SPRAYING
        update_static_display(st.session_state.grid_status)
        
        bar = progress_placeholder.progress(0, text=f"Spraying Grid ({r+1},{c+1})...")
        for i in range(100): time.sleep(0.1); bar.progress(i + 1)
        progress_placeholder.empty()

        st.session_state.grid_status[r, c] = STATE_SPRAYED
        st.session_state.tank_level = max(0, st.session_state.tank_level - amount)
        st.session_state.sprayed_plots_count += 1
        add_to_log(f"✅ Grid ({r+1},{c+1}) has been treated. Used {amount:.1f} L.")
        
        del st.session_state.manual_target
        st.session_state.system_status = "Idle"
        st.session_state.view = "dashboard"
        st.rerun()

    # --- Logic for Blanket Spray ---
    elif st.session_state.view == "blanket_spray":
        st.session_state.system_status = "Spraying"
        add_to_log("📢 Simultaneous blanket spray initiated for all grids.")
        
        BLANKET_SPRAY_AMOUNT = 1.5 # Fixed amount per grid for blanket spray (in L)

        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                st.session_state.grid_status[r, c] = STATE_SPRAYING
        update_static_display(st.session_state.grid_status)

        bar = progress_placeholder.progress(0, text=f"Spraying all 16 grids...")
        for i in range(100): time.sleep(0.15); bar.progress(i + 1)
        progress_placeholder.empty()

        plots_actually_sprayed = 0
        total_blanket_used = 0
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                if st.session_state.tank_level >= BLANKET_SPRAY_AMOUNT:
                    st.session_state.grid_status[r, c] = STATE_SPRAYED
                    st.session_state.tank_level -= BLANKET_SPRAY_AMOUNT
                    st.session_state.sprayed_plots_count += 1
                    plots_actually_sprayed += 1
                    total_blanket_used += BLANKET_SPRAY_AMOUNT
                else:
                    st.session_state.grid_status[r, c] = STATE_HEALTHY # Revert if no pesticide left
        
        if plots_actually_sprayed < GRID_ROWS * GRID_COLS:
            add_to_log(f"⚠️ Tank empty. Only {plots_actually_sprayed} grids were treated.")
        add_to_log(f"✅ Blanket spray complete. Used {total_blanket_used:.1f} L.")
        st.session_state.system_status = "Idle"
        st.session_state.view = "dashboard"
        st.rerun()
