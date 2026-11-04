/*
 * The group editor of an input (components/group_editor.py): selecting a configuration icon and the row to move it to.
 *
 * Selecting an icon never contacts the server. Choosing a row writes {mm_index, target} to the row's
 * group-move-request store, which react_to_input_change passes to the move handler; it redraws the editor. A move or
 * "Use for all" that would remove a Variable asks for confirmation first. Esc, selecting the icon again or clicking
 * outside the editor cancels a selection.
 */
(function () {
    function editorOf(el) {
        return el.closest('.group-editor');
    }

    function clearSelection(editor) {
        delete editor.dataset.selected;
        editor.querySelectorAll('.group-editor-icon.selected').forEach(function (x) {
            x.classList.remove('selected');
            x.setAttribute('aria-pressed', 'false');
        });
        editor.querySelectorAll('.group-editor-row.source').forEach(function (x) { x.classList.remove('source'); });
        hideConfirm(editor);
    }

    function clearAll(except) {
        document.querySelectorAll('.group-editor[data-selected]').forEach(function (x) {
            if (x !== except) { clearSelection(x); }
        });
    }

    function hideConfirm(editor) {
        const confirm = editor.querySelector('.group-editor-confirm');
        if (confirm) { confirm.hidden = true; }
        delete editor.dataset.pending;
    }

    function askConfirm(editor, text, request) {
        const confirm = editor.querySelector('.group-editor-confirm');
        confirm.querySelector('.group-editor-confirm-text').textContent = text;
        confirm.hidden = false;
        // The destination row is found again from the target when confirmed
        editor.dataset.pending = JSON.stringify(request);
        confirm.querySelector('.group-editor-confirm-yes').focus();
    }

    // e.g. "Variables used for groups: [3, 4], [2, 5] will be removed."
    function removalText(groups) {
        const plural = groups.length > 1 ? 's' : '';
        return 'Variable' + plural + ' used for group' + plural + ': '
            + groups.map(function (x) { return '[' + x.join(', ') + ']'; }).join(', ') + ' will be removed.';
    }

    // The configurations of a row's group, from 1
    function groupOf(row) {
        return Array.from(row.querySelectorAll('.group-editor-icon')).map(function (icon) {
            return Number(icon.dataset.mmIndex) + 1;
        });
    }

    function send(editor, request, destination) {
        const storeId = JSON.parse(editor.dataset.moveStore);
        request.time = Date.now();
        // Shown dimmed in its destination until the editor is redrawn
        const icon = request.mm_index === 'all' ? null
            : editor.querySelector('.group-editor-icon[data-mm-index="' + request.mm_index + '"]');
        if (destination) {
            destination.classList.add('pending');
            if (icon) {
                const ghost = icon.cloneNode(true);
                ghost.classList.add('ghost');
                ghost.classList.remove('selected', 'focussed');
                ghost.disabled = true;
                destination.querySelector('.group-editor-icons').appendChild(ghost);
            }
        }
        clearSelection(editor);
        window.dash_clientside.set_props(storeId, {data: request});
    }

    function selectIcon(editor, icon) {
        const wasSelected = icon.classList.contains('selected');
        clearAll(null);
        if (wasSelected) { return; }
        icon.classList.add('selected');
        icon.setAttribute('aria-pressed', 'true');
        editor.dataset.selected = icon.dataset.mmIndex;
        const row = icon.closest('.group-editor-row');
        row.classList.add('source');
        // A configuration alone in its group already has a value of its own
        editor.classList.toggle('source-alone', row.dataset.size === '1');
        const n = Number(icon.dataset.mmIndex) + 1;
        editor.querySelectorAll('.group-editor-row:not(.source) .group-editor-insert').forEach(function (x) {
            x.setAttribute('aria-label', 'Move Config ' + n + ' to ' + x.dataset.label);
            x.title = 'Move Config ' + n + ' here';
        });
    }

    function insert(editor, button) {
        const source = editor.querySelector('.group-editor-row.source');
        if (!source || !editor.dataset.selected) { return; }
        const destination = button.closest('.group-editor-row');
        const request = {mm_index: Number(editor.dataset.selected), target: button.dataset.target};
        if (source.dataset.size === '1' && request.target !== 'new') {
            askConfirm(editor, removalText([groupOf(source)]), request);
        } else {
            send(editor, request, destination);
        }
    }

    function useForAll(editor, button) {
        clearAll(null);
        const destination = button.closest('.group-editor-row');
        // Every other group's Variable would be removed
        const groups = [];
        editor.querySelectorAll('.group-editor-row[data-size]').forEach(function (x) {
            if (x !== destination) { groups.push(groupOf(x)); }
        });
        const request = {mm_index: 'all', target: button.dataset.target};
        askConfirm(editor, removalText(groups), request);
    }

    document.addEventListener('click', function (event) {
        const target = event.target;
        const editor = editorOf(target);
        if (!editor) {
            clearAll(null);
            return;
        }
        const icon = target.closest('.group-editor-icon');
        if (icon && !icon.disabled) {
            selectIcon(editor, icon);
            return;
        }
        const insertButton = target.closest('.group-editor-insert');
        if (insertButton) {
            insert(editor, insertButton);
            return;
        }
        const allButton = target.closest('.group-editor-all');
        if (allButton) {
            useForAll(editor, allButton);
            return;
        }
        if (target.closest('.group-editor-confirm-yes') && editor.dataset.pending) {
            const request = JSON.parse(editor.dataset.pending);
            const destination = editor.querySelector('.group-editor-row[data-var-uid="' + request.target + '"]');
            hideConfirm(editor);
            send(editor, request, destination);
            return;
        }
        if (target.closest('.group-editor-confirm-no')) {
            clearSelection(editor);
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            clearAll(null);
        }
    });
})();
