import streamlit as st
import numpy as np
import pandas as pd
from collections import deque
import math
import random

# Set page title and configuration
st.set_page_config(page_title="Memory Paging Simulator", layout="wide")

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-container {
        background-color: #f0f2f6;
        border-radius: 5px;
        padding: 15px;
        margin-bottom: 10px;
    }

    .page-table {
        border-collapse: collapse;
        width: 100%;
        margin: 10px 0;
    }

    .page-table th,
    .page-table td {
        border: 1px solid #2d333b;
        padding: 8px;
        text-align: left;
    }

    .page-table th {
        background-color: #1e1e1e;
        color: white;
        border-bottom: 2px solid #2d333b;
    }

    .page-table tr {
        border-bottom: 1px solid #2d333b;
    }

    .page-table tr:last-child {
        border-bottom: 2px solid #2d333b;
    }
    .page-fault {
        background-color: #ffdddd;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .present {
        color: green;
        font-weight: bold;
    }
    .not-present {
        color: red;
        font-weight: bold;
    }
    .fifo-queue {
        background-color: #e6f3ff;
        padding: 10px;
        border-radius: 5px;
    }
    .binary {
        font-family: monospace;
        background-color: #f0f0f0;
        padding: 2px 4px;
        border-radius: 3px;
    }
    .conversion-details {
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# Title of the app
st.title("Memory Paging Simulator")

# Helper functions for binary conversions and calculations
def dec_to_bin(num_bits, decimal_num):
    """Convert decimal to binary with specified number of bits"""
    if decimal_num < 0:
        return "0" * num_bits
    binary = bin(decimal_num)[2:]  # Remove '0b' prefix
    return binary.zfill(num_bits)  # Pad with zeros to reach num_bits

def bin_to_dec(binary_str):
    """Convert binary string to decimal"""
    return int(binary_str, 2)

class MemorySimulator:
    def __init__(self):
        self.virtual_size = 16  # Default 16 KB
        self.page_size = 2      # Default 2 KB
        self.physical_size = 8  # Default 8 KB (1/2 of virtual)
        self.memory_map = []    # Page table
        self.fifo_queue = deque()  # Queue for FIFO page replacement
        self.conversion_type = "virtual_to_phys"  # Default conversion type

        # Calculated values
        self.total_bits = 0
        self.offset_bits = 0
        self.index_bits = 0
        self.physical_address_bits = 0  # For physical memory addresses
        self.physical_frame_bits = 0    # For physical frame index bits
        self.num_virtual_pages = 0
        self.num_physical_frames = 0

    def calculate_memory_parameters(self):
        """Calculate memory parameters based on user inputs"""
        # Convert KB to bytes
        virtual_bytes = self.virtual_size * 1024
        page_bytes = self.page_size * 1024
        physical_bytes = self.physical_size * 1024

        # Calculate virtual address bits
        self.total_bits = int(math.log2(virtual_bytes))
        self.offset_bits = int(math.log2(page_bytes))
        self.index_bits = self.total_bits - self.offset_bits

        # Calculate physical address bits
        self.physical_address_bits = int(math.log2(physical_bytes))
        self.physical_frame_bits = self.physical_address_bits - self.offset_bits

        # Calculate number of pages and frames
        self.num_virtual_pages = 2 ** self.index_bits
        self.num_physical_frames = 2 ** self.physical_frame_bits

        # Initialize the memory map
        self.initialize_memory_map()

    def initialize_memory_map(self):
        """Initialize the memory map (page table)"""
        self.memory_map = []
        for i in range(self.num_virtual_pages):
            self.memory_map.append({
                'virtual_index': i,
                'virtual_binary': dec_to_bin(self.index_bits, i),
                'physical_index': None,
                'physical_binary': None,
                'present': False
            })

        # Clear FIFO queue
        self.fifo_queue = deque()

    def update_page_table(self, virtual_page, physical_page, present):
        """Update a specific entry in the page table"""
        self.memory_map[virtual_page]['physical_index'] = physical_page
        self.memory_map[virtual_page]['physical_binary'] = dec_to_bin(self.physical_frame_bits, physical_page) if physical_page is not None else None
        self.memory_map[virtual_page]['present'] = present

        # Update FIFO queue if page is present
        if present and physical_page is not None:
            # Remove if already in queue (shouldn't happen in normal operation)
            if virtual_page in self.fifo_queue:
                self.fifo_queue.remove(virtual_page)
            # Add to queue
            self.fifo_queue.append(virtual_page)

    def convert_address(self, address):
        """Convert address between virtual and physical based on the current setting"""
        try:
            address_dec = int(address)
            address_bin = dec_to_bin(self.total_bits, address_dec)

            # Split address into page index and offset
            page_index_bin = address_bin[:self.index_bits]
            offset_bin = address_bin[self.index_bits:]

            page_index = bin_to_dec(page_index_bin)
            offset = bin_to_dec(offset_bin)

            # Results dictionary to return
            result = {
                'original_address_dec': address_dec,
                'original_address_bin': address_bin,
                'page_index_bin': page_index_bin,
                'page_index_dec': page_index,
                'offset_bin': offset_bin,
                'offset_dec': offset,
                'page_fault': False,
                'page_replaced': None,
                'converted_address_bin': None,
                'converted_address_dec': None,
                'result_status': 'success'
            }

            if self.conversion_type == "virtual_to_phys":
                # Check if the page is present
                if not self.memory_map[page_index]['present']:
                    # Page fault! Handle with FIFO
                    result['page_fault'] = True
                    self.handle_page_fault(page_index, result)

                # Get the physical frame
                physical_frame = self.memory_map[page_index]['physical_index']
                physical_frame_bin = dec_to_bin(self.physical_frame_bits, physical_frame)

                # Combine with offset to get physical address
                physical_address_bin = physical_frame_bin + offset_bin
                physical_address_dec = bin_to_dec(physical_address_bin)

                result['converted_address_bin'] = physical_address_bin
                result['converted_address_dec'] = physical_address_dec

            elif self.conversion_type == "phys_to_virtual":
                # In physical to virtual conversion, we need to search for the physical frame
                # For physical addresses, the index part may be different in size than virtual address index
                physical_address_bin = dec_to_bin(self.physical_address_bits, address_dec)
                physical_frame_bin = physical_address_bin[:self.physical_frame_bits]
                offset_bin = physical_address_bin[self.physical_frame_bits:]

                physical_frame = bin_to_dec(physical_frame_bin)
                offset = bin_to_dec(offset_bin)

                # Update result with physical frame info
                result['page_index_bin'] = physical_frame_bin
                result['page_index_dec'] = physical_frame
                result['offset_bin'] = offset_bin
                result['offset_dec'] = offset

                # Find which virtual page maps to this physical frame
                virtual_page = None
                for i, entry in enumerate(self.memory_map):
                    if entry['present'] and entry['physical_index'] == physical_frame:
                        virtual_page = i
                        break

                if virtual_page is None:
                    result['result_status'] = 'error'
                    result['error_message'] = f"No virtual page maps to physical frame {physical_frame}"
                    return result

                # Get the virtual address
                virtual_page_bin = dec_to_bin(self.index_bits, virtual_page)
                virtual_address_bin = virtual_page_bin + offset_bin
                virtual_address_dec = bin_to_dec(virtual_address_bin)

                result['converted_address_bin'] = virtual_address_bin
                result['converted_address_dec'] = virtual_address_dec

            return result

        except Exception as e:
            return {
                'result_status': 'error',
                'error_message': f"Error converting address: {str(e)}"
            }

    def handle_page_fault(self, virtual_page, result):
        """Handle page fault using FIFO replacement algorithm"""
        # Check if there's space available in physical memory
        assigned_frames = sum(1 for entry in self.memory_map if entry['present'])

        if assigned_frames < self.num_physical_frames:
            # There's free space, assign a new frame
            new_frame = assigned_frames
            self.update_page_table(virtual_page, new_frame, True)

            # Make sure the page is added to the FIFO queue
            if virtual_page not in self.fifo_queue:
                self.fifo_queue.append(virtual_page)

            # Log the action
            st.session_state.page_fault_log.append(f"Page fault: Virtual page {virtual_page} loaded into free frame {new_frame}")
        else:
            # Need to replace using FIFO
            page_to_replace = self.fifo_queue.popleft()
            replaced_frame = self.memory_map[page_to_replace]['physical_index']

            # Mark the replaced page as not present
            self.update_page_table(page_to_replace, None, False)

            # Assign the freed frame to the new page
            self.update_page_table(virtual_page, replaced_frame, True)

            # Add the new page to the FIFO queue
            self.fifo_queue.append(virtual_page)

            # Record the replacement in the result
            result['page_replaced'] = page_to_replace

            # Log the action
            st.session_state.page_fault_log.append(f"Page fault: Virtual page {virtual_page} replaced page {page_to_replace} in frame {replaced_frame}")

# Initialize the session state if it doesn't exist
if 'simulator' not in st.session_state:
    st.session_state.simulator = MemorySimulator()
    st.session_state.page_table_initialized = False
    st.session_state.address_results = []
    st.session_state.page_fault_log = []

# Function to restart the simulation
def restart_simulation():
    st.session_state.simulator = MemorySimulator()
    st.session_state.page_table_initialized = False
    st.session_state.address_results = []
    st.session_state.page_fault_log = []

    # Clear the FIFO replacement data when restarting
    if 'fifo_replacement_data' in st.session_state:
        del st.session_state.fifo_replacement_data

# Create a sidebar for inputs
with st.sidebar:
    st.header("Memory Configuration")

    # Input for virtual memory size
    virtual_size = st.number_input(
        "Virtual Memory Size (KB)", 
        min_value=4, 
        value=16, 
        step=4,
        help="Size of virtual memory in KB. Must be a power of 2."
    )

    # Input for page size
    page_size = st.number_input(
        "Page Size (KB)", 
        min_value=1, 
        value=2, 
        step=1,
        help="Size of each page in KB. Must be a power of 2 and smaller than virtual memory size."
    )

    # Physical memory is automatically set to half of virtual memory
    physical_size = virtual_size // 2
    st.write(f"Physical Memory Size: {physical_size} KB (1/2 of Virtual Memory)")

    # Conversion type selection
    conversion_type = st.selectbox(
        "Conversion Type",
        ["virtual_to_phys", "phys_to_virtual"],
        format_func=lambda x: "Virtual to Physical" if x == "virtual_to_phys" else "Physical to Virtual"
    )

    # Button to initialize the memory configuration
    if st.button("Initialize Memory"):
        # Validate inputs
        valid_input = True
        error_message = ""

        # Check if virtual size is a power of 2
        if virtual_size & (virtual_size - 1) != 0:
            valid_input = False
            error_message += "Virtual Memory Size must be a power of 2. "

        # Check if page size is a power of 2
        if page_size & (page_size - 1) != 0:
            valid_input = False
            error_message += "Page Size must be a power of 2. "

        # Check if page size is smaller than virtual size
        if page_size >= virtual_size:
            valid_input = False
            error_message += "Page Size must be smaller than Virtual Memory Size. "

        # Check if virtual size is divisible by page size
        if virtual_size % page_size != 0:
            valid_input = False
            error_message += "Virtual Memory Size must be divisible by Page Size. "

        if valid_input:
            # Set memory parameters
            simulator = st.session_state.simulator
            simulator.virtual_size = virtual_size
            simulator.page_size = page_size
            simulator.physical_size = physical_size
            simulator.conversion_type = conversion_type

            # Calculate memory parameters and initialize page table
            simulator.calculate_memory_parameters()

            # Update session state
            st.session_state.page_table_initialized = True
            st.session_state.address_results = []
            st.session_state.page_fault_log = []

            st.success("Memory configuration initialized successfully!")
        else:
            st.error(error_message)

    # Button to restart simulation
    if st.button("Restart Simulation"):
        restart_simulation()
        st.success("Simulation restarted!")

# Main content area
if not st.session_state.page_table_initialized:
    # Display instructions when not initialized
    st.info("Please configure memory parameters in the sidebar and click 'Initialize Memory' to start.")

    # Display brief explanation about memory paging
    st.subheader("Memory Paging Concept")
    st.write("""
    Memory paging is a memory management scheme that eliminates the need for contiguous allocation of physical memory.
    - Virtual addresses are divided into a page number and an offset
    - The page table maps virtual pages to physical frames
    - Page faults occur when a referenced page is not in physical memory
    """)
else:
    # Display memory parameters in the style shown in the image
    simulator = st.session_state.simulator

    # Calculate the max addresses
    virtual_max_address = (2**simulator.total_bits) - 1
    physical_max_address = (2**simulator.physical_address_bits) - 1

    # Add CSS for memory configuration cards
    st.markdown("""
    <style>
    .memory-card {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    .memory-header {
        color: #ffffff;
        font-size: 1.2em;
        margin-bottom: 5px;
    }
    .memory-value {
        color: white;
        font-size: 1.8em;
        margin: 10px 0;
    }
    .divider {
        border-top: 1px solid #333;
        margin: 15px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # Create three columns for different sets of parameters
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class='memory-card'>
            <div class='memory-header'>Virtual Memory Size</div>
            <div class='memory-value'>{} KB</div>
            <div class='divider'></div>
            <div class='memory-header'>Virtual Address Bits</div>
            <div class='memory-value'>{}</div>
            <div class='divider'></div>
            <div class='memory-header'>Page Index Bits</div>
            <div class='memory-value'>{}</div>
            <div class='divider'></div>
            <div class='memory-header'>Number of Virtual Pages</div>
            <div class='memory-value'>{}</div>
            <div class='divider'></div>
            <div class='memory-header'>Address Range</div>
            <div class='memory-value'>0x0 - 0x{:X}</div>
        </div>
        """.format(
            simulator.virtual_size,
            simulator.total_bits,
            simulator.index_bits,
            simulator.num_virtual_pages,
            virtual_max_address
        ), unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class='memory-card'>
            <div class='memory-header'>Physical Memory Size</div>
            <div class='memory-value'>{} KB</div>
            <div class='divider'></div>
            <div class='memory-header'>Physical Address Bits</div>
            <div class='memory-value'>{}</div>
            <div class='divider'></div>
            <div class='memory-header'>Physical Frame Bits</div>
            <div class='memory-value'>{}</div>
            <div class='divider'></div>
            <div class='memory-header'>Number of Physical Frames</div>
            <div class='memory-value'>{}</div>
            <div class='divider'></div>
            <div class='memory-header'>Address Range</div>
            <div class='memory-value'>0x0 - 0x{:X}</div>
        </div>
        """.format(
            simulator.physical_size,
            simulator.physical_address_bits,
            simulator.physical_frame_bits,
            simulator.num_physical_frames,
            physical_max_address
        ), unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class='memory-card'>
            <div class='memory-header'>Page Size</div>
            <div class='memory-value'>{} KB</div>
            <div class='divider'></div>
            <div class='memory-header'>Offset Bits</div>
            <div class='memory-value'>{}</div>
            <div class='divider'></div>
            <div class='memory-header'>Replacement Algorithm</div>
            <div class='memory-value'>FIFO</div>
            <div class='divider'></div>
            <div class='memory-header'>Conversion Type</div>
            <div class='memory-value'>{}</div>
        </div>
        """.format(
            simulator.page_size,
            simulator.offset_bits,
            'Virtual to Physical' if simulator.conversion_type == 'virtual_to_phys' else 'Physical to Virtual'
        ), unsafe_allow_html=True)

    # Removed the "Memory Address Ranges Details" section as requested

    # Manual Page Table Configuration Section
    st.subheader("Page Table Configuration")

    # Add Random Mapping button above the expander
    if st.button("Random Mapping"):
        # Get simulator instance
        simulator = st.session_state.simulator

        # Clear any existing mappings
        for entry in simulator.memory_map:
            entry['present'] = False
            entry['physical_index'] = None
            entry['physical_binary'] = None

        # Clear FIFO queue
        simulator.fifo_queue = deque()

        # Get available physical frames
        num_physical_frames = simulator.num_physical_frames

        # Select random virtual pages (up to the number of physical frames)
        available_virtual_pages = list(range(simulator.num_virtual_pages))
        selected_pages = random.sample(available_virtual_pages, num_physical_frames)

        # Assign random frames to the selected pages
        available_frames = list(range(num_physical_frames))
        random.shuffle(available_frames)

        # Update page table with random mapping
        for i, page_idx in enumerate(selected_pages):
            frame_idx = available_frames[i]
            simulator.update_page_table(page_idx, frame_idx, True)

        st.success(f"Random mapping created! {num_physical_frames} pages randomly assigned to physical frames.")

    # Add feature to manually set page table entries
    with st.expander("Configure Page Table Entries and Arrival Order"):
        st.write("Set which virtual pages are present in physical memory and their corresponding physical frames.")

        # Flag to track if any changes were made to the page table
        page_table_changed = False

        # Get number of available physical frames
        num_physical_frames = simulator.num_physical_frames

        # Create a list of all potential physical frames
        available_frames = list(range(num_physical_frames))

        # Count already present pages before iterating
        initially_present_count = sum(1 for entry in simulator.memory_map if entry['present'])
        max_allowed_pages = simulator.num_physical_frames

        # Display frame capacity information in a custom styled div
        st.markdown(f"""
        <div style="background-color: #1E4D75; color: white; padding: 8px 16px; border-radius: 4px; margin: 4px 0;">
            Physical memory has {max_allowed_pages} frames available. You can mark at most {max_allowed_pages} virtual pages as present.
        </div>
        """, unsafe_allow_html=True)

        # Create columns for the table header with improved alignment
        col1, col2, col3 = st.columns([2, 1, 2])
        col1.write("**Virtual Page**")
        col2.write("**Present**")
        col3.write("**Physical Frame**")

        # Used to track which frames are already assigned
        used_frames = set()
        arrival_order_list = []

        # Track pages that are newly marked as present vs those already present
        current_present_count = 0

        # For each virtual page, create a row of inputs
        for i, entry in enumerate(simulator.memory_map):
            cols = st.columns([2, 1, 2])

            # Virtual page (display only) - Now with page index
            cols[0].write(f"{i}: `{entry['virtual_binary']}`")

            # Present bit (checkbox)
            was_present = entry['present']

            # Reset the counter and count all present pages to get an accurate count
            current_present_count = sum(1 for e in simulator.memory_map if e['present'])

            # If we've reached the max pages and this page wasn't already present, disable the checkbox
            checkbox_disabled = (current_present_count >= max_allowed_pages) and not was_present

            # Set the help text based on whether the checkbox is disabled
            help_text = "Maximum number of pages reached" if checkbox_disabled else ""

            # Present bit (checkbox) - disable if we're at max capacity
            present = cols[1].checkbox("", value=was_present, key=f"present_{i}", disabled=checkbox_disabled, help=help_text)

            # We'll recount after changes for accuracy

            # Physical frame (selectbox, only enabled if present is checked)
            used_frame = entry['physical_index'] if entry['physical_index'] is not None else -1

            if present:
                # If this frame was already present, don't count it as "used" for other pages
                if used_frame >= 0:
                    frame_options = [used_frame] + [f for f in available_frames if f not in used_frames or f == used_frame]
                else:
                    # Auto-assign the next available frame (lowest numbered free frame)
                    available_free_frames = [f for f in available_frames if f not in used_frames]
                    # Default to automatically selecting the first available frame
                    if available_free_frames:
                        auto_frame = min(available_free_frames)
                        frame_options = [auto_frame] + [f for f in available_frames if f not in used_frames or f == auto_frame]
                    else:
                        frame_options = [f for f in available_frames if f not in used_frames]

                # If no frames available, select first one and display a warning
                if not frame_options:
                    frame_options = [0]
                    st.error("""
                    ⚠️ **Memory Allocation Error**: More pages selected as present than available physical frames!

                    **What this means**: In a paging system, each present virtual page must map to a unique physical frame.
                    Your physical memory only has enough frames to accommodate a limited number of pages at once.

                    **How to fix this**: Uncheck some 'Present' checkboxes to reduce the number of active pages.
                    """)

                physical_frame = cols[2].selectbox(
                    "", 
                    options=frame_options,
                    index=0,  # Always select the first option (which is either the existing frame or the auto-assigned one)
                    key=f"frame_{i}"
                )

                # Mark this frame as used
                used_frames.add(physical_frame)

                # Add to arrival order list
                arrival_order_list.append((i, physical_frame))
            else:
                # Display disabled selectbox if not present
                cols[2].selectbox(
                    "", 
                    options=[-1], 
                    format_func=lambda x: "N/A",
                    disabled=True,
                    key=f"frame_disabled_{i}"
                )
                physical_frame = None

            # Check if page table entry changed
            if (present != entry['present']) or (present and physical_frame != entry['physical_index']):
                page_table_changed = True
                simulator.update_page_table(i, physical_frame, present)

        # Arrival order configuration
        st.write("---")
        st.write("**Configure FIFO Queue Arrival Order**")
        st.write("Drag to reorder the pages in the FIFO queue (oldest first):")

        # Get only the present pages
        present_pages = [(i, entry) for i, entry in enumerate(simulator.memory_map) if entry['present']]

        if present_pages:
            # Create a list of present pages to be displayed in arrival order editor
            arrival_options = []
            for i, entry in present_pages:
                virt_page = entry['virtual_binary']
                phys_frame = entry['physical_binary']
                arrival_options.append({"id": i, "label": f"Virtual Page {virt_page} → Physical Frame {phys_frame}"})

            if 'fifo_order' not in st.session_state:
                # Initialize with current FIFO queue if it exists
                if simulator.fifo_queue:
                    st.session_state.fifo_order = list(simulator.fifo_queue)
                else:
                    # Initialize with pages in numerical order
                    st.session_state.fifo_order = [entry["id"] for entry in arrival_options]

            # Reorder if necessary to show only present pages and remove non-present ones
            present_ids = [entry["id"] for entry in arrival_options]
            st.session_state.fifo_order = [id for id in st.session_state.fifo_order if id in present_ids]
            for id in present_ids:
                if id not in st.session_state.fifo_order:
                    st.session_state.fifo_order.append(id)

            # Display the current order
            fifo_editor_cols = st.columns(len(st.session_state.fifo_order))
            for i, page_id in enumerate(st.session_state.fifo_order):
                # Find the label for this page
                label = next((entry["label"] for entry in arrival_options if entry["id"] == page_id), f"Page {page_id}")
                fifo_editor_cols[i].write(f"{i+1}. {label}")

            # Create a multi-select for reordering
            new_order = st.multiselect(
                "Select pages in desired arrival order (oldest first):",
                options=arrival_options,
                default=arrival_options,
                format_func=lambda x: x["label"],
                key="fifo_reorder"
            )

            # Update FIFO queue if order changed
            if st.button("Update Arrival Order"):
                if new_order:
                    new_order_ids = [item["id"] for item in new_order]
                    if new_order_ids != st.session_state.fifo_order:
                        # Update the FIFO queue
                        simulator.fifo_queue = deque(new_order_ids)
                        st.session_state.fifo_order = new_order_ids
                        st.success("FIFO queue order updated!")
                        page_table_changed = True
                else:
                    st.error("Please select at least one page for the FIFO queue")
        else:
            st.info("No pages are currently present in physical memory. Add pages to configure arrival order.")

    # Display page table
    st.subheader("Page Table")

    # Create a DataFrame for the page table
    page_table_data = []
    for entry in simulator.memory_map:
        in_queue = entry['virtual_index'] in simulator.fifo_queue
        queue_pos = list(simulator.fifo_queue).index(entry['virtual_index']) + 1 if in_queue else None

        page_table_data.append({
            "Page Index": entry['virtual_index'],
            "Virtual Page": entry['virtual_binary'],
            "Physical Frame": entry['physical_binary'] if entry['present'] else "Not Present",
            "Present Bit": "1" if entry['present'] else "0",
            "In FIFO Queue": f"Yes (Position {queue_pos})" if in_queue else "No"
        })

    page_table_df = pd.DataFrame(page_table_data)
    st.dataframe(page_table_df, use_container_width=True)

    # Display FIFO queue
    if simulator.fifo_queue:
        st.subheader("FIFO Page Replacement Queue")
        st.write("Pages in order of arrival (oldest first):")
        fifo_display = [f"Page {dec_to_bin(simulator.index_bits, page)}" for page in simulator.fifo_queue]
        st.code(" → ".join(fifo_display))

    # Display the updated page table if there was a FIFO replacement
    if 'fifo_replacement_data' in st.session_state:
        st.subheader("Page Table After FIFO Replacement")

        # Get the data
        page_table_data = st.session_state.fifo_replacement_data['page_table_data']
        replaced_page = st.session_state.fifo_replacement_data['replaced_page']
        added_page = st.session_state.fifo_replacement_data['added_page']

        # Create a dataframe
        updated_df = pd.DataFrame(page_table_data)

        # Apply styling to highlight only row borders with specific colors
        def highlight_changes(row):
            if row['Status'] == 'REPLACED OUT':
                return ['border: 2px solid #FF0000'] * len(row)
            elif row['Status'] == 'ADDED TO MEMORY':
                return ['border: 2px solid #008000'] * len(row)
            else:
                return [''] * len(row)

        styled_df = updated_df.style.apply(highlight_changes, axis=1)
        st.dataframe(styled_df, use_container_width=True)


    # Display page fault log
    if st.session_state.page_fault_log:
        with st.expander("Page Fault History", expanded=True):
            st.write("Recent page faults and replacements:")
            for log_entry in st.session_state.page_fault_log[-5:]:
                st.info(log_entry)

    # Form for address conversion
    st.subheader("Address Conversion")

    with st.form("address_conversion_form"):
        if simulator.conversion_type == "virtual_to_phys":
            address_label = "Virtual Address"
            convert_button_label = "Convert to Physical Address"
        else:
            address_label = "Physical Address"
            convert_button_label = "Convert to Virtual Address"

        # Use only hexadecimal format
        help_text = "Enter a hexadecimal address (e.g., 0x2A or 2A)"
        address_input = st.text_input(address_label, help=help_text)
        convert_submitted = st.form_submit_button(convert_button_label)

        if convert_submitted and address_input:
            try:
                # Handle hex input with or without 0x prefix
                if address_input.lower().startswith('0x'):
                    address = int(address_input, 16)
                else:
                    address = int(address_input, 16)

                max_address = 2**simulator.total_bits - 1

                if address < 0 or address > max_address:
                    st.error(f"Address must be between 0x0 and 0x{max_address:X}")
                else:
                    result = simulator.convert_address(address)

                    if result['result_status'] == 'success':
                        # Add the result to the history
                        st.session_state.address_results.append(result)

                        # Display conversion information
                        st.success("Address conversion successful!")

                        st.markdown("## Conversion Details")

                        # Left side information in single column layout
                        st.markdown("### Original Address:")
                        st.markdown(f"**Hex:** `0x{result['original_address_dec']:X}`", unsafe_allow_html=True)

                        st.markdown(f"### Page Index [{simulator.index_bits} bits]:")
                        st.markdown(f"**Hex:** `0x{result['page_index_dec']:X}`", unsafe_allow_html=True)

                        st.markdown(f"### Offset [{simulator.offset_bits} bits]:")
                        st.markdown(f"**Hex:** `0x{result['offset_dec']:X}`", unsafe_allow_html=True)

                                                # Right side information now below left side
                        st.markdown("### Converted Address:")
                        st.markdown(f"**Hex:** `0x{result['converted_address_dec']:X}`", unsafe_allow_html=True)

                        # Optionally show binary representation in collapsible section
                        with st.expander("Show Binary Representation"):
                            st.markdown(f"**Original Address (Binary):** `{result['original_address_bin']}`")
                            st.markdown(f"**Page Index (Binary, {simulator.index_bits} bits):** `{result['page_index_bin']}`")
                            st.markdown(f"**Offset (Binary, {simulator.offset_bits} bits):** `{result['offset_bin']}`")
                            st.markdown(f"**Converted Address (Binary):** `{result['converted_address_bin']}`")

                        # Show page fault notice if applicable
                        if result['page_fault']:
                            # Use custom styling to match the screenshot
                            st.markdown("""
                            <div style="background-color: #FFC107; color: #212121; padding: 16px; border-radius: 4px; margin-top: 16px; display: flex; align-items: center;">
                                <span style="font-size: 24px; margin-right: 12px;">⚠️</span>
                                <span style="font-weight: bold; font-size: 18px;">Page fault occurred!</span>
                            </div>
                            """, unsafe_allow_html=True)

                            if result['page_replaced'] is not None:
                                page_binary = dec_to_bin(simulator.index_bits, result['page_replaced'])
                                replaced_page = result['page_replaced']

                                # Show replacement info with styling similar to screenshot
                                st.markdown(f"""
                                <div style="background-color: #1E4D75; color: white; padding: 16px; border-radius: 4px; margin-top: 16px;">
                                    <span style="font-weight: bold; font-size: 16px;">Page 0x{replaced_page:X} (binary: {page_binary}) was replaced using FIFO</span>
                                </div>
                                """, unsafe_allow_html=True)

                                # Update the Page Table display to show the current state after FIFO replacement
                                st.markdown("""
                                <div style="background-color: #165F33; color: white; padding: 16px; border-radius: 4px; margin-top: 16px;">
                                    <span style="font-weight: bold; font-size: 16px;">Page table updated with FIFO replacement</span>
                                </div>
                                """, unsafe_allow_html=True)

                                # Create dataframe with the current memory map
                                page_table_data = []
                                for entry in simulator.memory_map:
                                    in_queue = entry['virtual_index'] in simulator.fifo_queue

                                    # Add a note to indicate which pages were involved in replacement
                                    status = ""
                                    if entry['virtual_index'] == replaced_page:
                                        status = "REPLACED OUT"
                                    elif entry['virtual_index'] == result['page_index_dec']:
                                        status = "ADDED TO MEMORY"

                                    page_table_data.append({
                                        "Page Index": entry['virtual_index'],
                                        "Virtual Page": entry['virtual_binary'],
                                        "Physical Frame": entry['physical_binary'] if entry['present'] else "Not Present",
                                        "Present Bit": "1" if entry['present'] else "0",
                                        "In FIFO Queue": "Yes" if in_queue else "No",
                                        "Status": status
                                    })

                                # Store the data in session state to display under the original page table
                                st.session_state.fifo_replacement_data = {
                                    'page_table_data': page_table_data,
                                    'replaced_page': replaced_page,
                                    'added_page': result['page_index_dec']
                                }

                                # Display the updated page table right here as well
                                st.subheader("Page Table After FIFO Replacement")
                                updated_df = pd.DataFrame(page_table_data)

                                # Apply styling to highlight only row borders with specific colors
                                def highlight_changes(row):
                                    if row['Status'] == 'REPLACED OUT':
                                        return ['border: 2px solid #FF0000'] * len(row)
                                    elif row['Status'] == 'ADDED TO MEMORY':
                                        return ['border: 2px solid #008000'] * len(row)
                                    else:
                                        return [''] * len(row)

                                styled_df = updated_df.style.apply(highlight_changes, axis=1)
                                st.dataframe(styled_df, use_container_width=True)

                                # Also show the current FIFO queue state
                                st.subheader("Current FIFO Queue (after replacement)")
                                fifo_display = [f"Page {dec_to_bin(simulator.index_bits, page)}" for page in simulator.fifo_queue]
                                st.code(" → ".join(fifo_display))

                    else:
                        st.error(f"Error in conversion: {result.get('error_message', 'Unknown error')}")
            except ValueError:
                st.error("Please enter a valid hexadecimal number (e.g., 0x2A or 2A)")

    # Display conversion history
    if st.session_state.address_results:
        st.subheader("Conversion History")

        # Display most recent conversions first
        for i, result in enumerate(reversed(st.session_state.address_results[-5:])):
            with st.expander(f"Conversion #{len(st.session_state.address_results) - i}"):
                if simulator.conversion_type == "virtual_to_phys":
                    st.write(f"Virtual Address 0x{result['original_address_dec']:X} → Physical Address 0x{result['converted_address_dec']:X}")
                else:
                    st.write(f"Physical Address 0x{result['original_address_dec']:X} → Virtual Address 0x{result['converted_address_dec']:X}")

                if result['page_fault']:
                    st.markdown("""
                    <div style="background-color: #FFC107; color: #212121; padding: 10px; border-radius: 4px; margin-top: 10px; display: flex; align-items: center;">
                        <span style="font-size: 18px; margin-right: 8px;">⚠️</span>
                        <span style="font-weight: bold;">Page fault occurred!</span>
                    </div>
                    """, unsafe_allow_html=True)

                    if result['page_replaced'] is not None:
                        page_binary = dec_to_bin(simulator.index_bits, result['page_replaced'])
                        replaced_page = result['page_replaced']
                        st.markdown(f"""
                        <div style="background-color: #1E4D75; color: white; padding: 10px; border-radius: 4px; margin-top: 10px;">
                            <span>Page 0x{replaced_page:X} (binary: {page_binary}) was replaced using FIFO</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
