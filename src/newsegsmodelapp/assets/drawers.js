
window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        attach_drawer: function(_) {
            var drawers = document.getElementsByClassName('drawer-container');
            var headers = document.getElementsByClassName('drawer-header');
            var contents = document.getElementsByClassName('drawer-content');
            var handles = document.getElementsByClassName('resize-handle');
            var toggles = document.getElementsByClassName('annual-horizon-toggle');


            /** 
            var drawer = document.getElementById('drawer-container');
            var header = document.getElementById('drawer-header');
            var content = document.getElementById('drawer-content');
            var handle = document.getElementById('resize-handle');
            var toggle = document.getElementById('annual-horizon-toggle');
            */

            let isResizing = false;
            let isSideBySide = false;

            /**
             * Check if we should use side-by-side layout
             * Conditions: viewport width >= 992px (Bootstrap lg) AND landscape (width > height)
             */
            function shouldUseSideBySide() {
                const width = window.innerWidth;
                const height = window.innerHeight;
                return width >= 992 && width > height;
            }

            /**
             * Update layout mode based on viewport size
             */
            function updateLayoutMode() {
                const newMode = shouldUseSideBySide();

                if (newMode !== isSideBySide) {
                    isSideBySide = newMode;
                }
            }

            // Initial layout setup
            updateLayoutMode();

            function handleMouseMove(e) {
                if (!isResizing) return;

                // Calculate new height based on mouse position from bottom
                var newHeight = window.innerHeight - e.clientY;

                if (newHeight > 80 && newHeight < window.innerHeight * 0.9) {
                    for(let drawer of drawers){
                        drawer.style.transition = 'none';
                        drawer.style.height = `${newHeight}px`;
                    }
                    for(let content of contents){
                        content.style.display = 'block';
                    }
                }
            }

            let restore_height = '50vh';

            // 1. Click to toggle 50% height (only in drawer mode)
            for (const header of headers){
                header.addEventListener('click', (e) => {
                    if (isSideBySide) return;
                    if (isResizing) return;
                    if (e.target.closest && e.target.closest('#annual-horizon-toggle')) return;
                    if (e.target.closest && e.target.closest('button')) return;

                    for(const drawer of drawers){
                        if (!(drawer.style.height == '') && drawer.style.height != '80px') {
                            restore_height = drawer.style.height || restore_height;
                            drawer.style.height = '80px';
                        } else {
                            drawer.style.height = restore_height;
                        }
                    }
                    for (const content of contents){
                        if (!(drawer.style.height == '') && drawer.style.height != '80px') {
                            content.style.display = 'none';
                        } else {
                            content.style.display = 'block';
                        }
                    }
                    
                });
            }
            

            // 2. Drag to resize logic (only in drawer mode)
            for(const handle of handles){
                handle.addEventListener('mousedown', (e) => {
                    if (isSideBySide) return;
                    isResizing = true;
                    document.addEventListener('mousemove', handleMouseMove);
                    document.addEventListener('mouseup', () => {
                        isResizing = false;
                        for(let drawer of drawers){
                            drawer.style.transition = '';
                        }
                        document.removeEventListener('mousemove', handleMouseMove);
                    });
                });
            }
            

            window.addEventListener('resize', updateLayoutMode);
            window.addEventListener('orientationchange', updateLayoutMode);

            return _;
        }
    }
});
