
window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        attach_drawer: function(_) {
            var drawer = document.getElementById('drawer-container');
            var header = document.getElementById('drawer-header');
            var content = document.getElementById('drawer-content');
            var handle = document.getElementById('resize-handle');
            var toggle = document.getElementById('annual-horizon-toggle');

            let isResizing = false;

            function handleMouseMove(e) {
                if (!isResizing) return;

                // Calculate new height based on mouse position from bottom
                var newHeight = window.innerHeight - e.clientY;

                if (newHeight > 80 && newHeight < window.innerHeight * 0.9) {
                    drawer.style.transition = 'none';
                    drawer.style.height = `${newHeight}px`;
                    content.style.display = 'block';
                }
            }

            let restore_height = '50vh';

            // 1. Click to toggle 50% height
            header.addEventListener('click', (e) => {
                if (isResizing) return;
                if (toggle && e.target.closest && e.target.closest('#annual-horizon-toggle')) return;

                if (!(drawer.style.height == '') && drawer.style.height != '80px') {
                    restore_height = drawer.style.height || restore_height;
                    drawer.style.height = '80px';
                    content.style.display = 'none';
                } else {
                    drawer.style.height = restore_height;
                    content.style.display = 'block';
                }
            });

            // 2. Drag to resize logic
            handle.addEventListener('mousedown', (e) => {
                isResizing = true;
                document.addEventListener('mousemove', handleMouseMove);
                document.addEventListener('mouseup', () => {
                    isResizing = false;
                    document.removeEventListener('mousemove', handleMouseMove);
                });
            });

            return 1;
        }
    }
});
