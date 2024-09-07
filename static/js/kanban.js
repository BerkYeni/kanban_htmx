console.log('Kanban script loaded');

function initKanban() {
    console.log('Initializing Kanban');
    const columns = document.querySelectorAll('.column');
    const tasks = document.querySelectorAll('.task');

    console.log('Columns:', columns.length);
    console.log('Tasks:', tasks.length);

    if (columns.length === 0 || tasks.length === 0) {
        console.log('No columns or tasks found. DOM might not be ready. Retrying in 500ms.');
        setTimeout(initKanban, 500);
        return;
    }

    tasks.forEach(task => {
        task.addEventListener('dragstart', dragStart);
        task.addEventListener('dragend', dragEnd);
    });

    columns.forEach(column => {
        column.addEventListener('dragover', dragOver);
        column.addEventListener('dragenter', dragEnter);
        column.addEventListener('dragleave', dragLeave);
        column.addEventListener('drop', drop);
    });

    function dragStart(e) {
        console.log('Drag started', e.target.id);
        e.dataTransfer.setData('text/plain', e.target.id);
        this.classList.add('dragging');
    }

    function dragEnd() {
        console.log('Drag ended');
        this.classList.remove('dragging');
    }

    function dragOver(e) {
        e.preventDefault();
        console.log('Drag over');
    }

    function dragEnter(e) {
        e.preventDefault();
        this.classList.add('drag-over');
        console.log('Drag enter');
    }

    function dragLeave() {
        this.classList.remove('drag-over');
        console.log('Drag leave');
    }

    function drop(e) {
        e.preventDefault();
        console.log('Drop');
        this.classList.remove('drag-over');
        const taskId = e.dataTransfer.getData('text');
        const task = document.getElementById(taskId);
        const columnId = this.id.split('-')[1];
        
        this.querySelector('.tasks').appendChild(task);

        // Update task position in the backend
        fetch(`/tasks/${taskId.split('-')[1]}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                column_id: columnId,
                order: Array.from(this.querySelector('.tasks').children).indexOf(task)
            }),
        }).then(response => response.json())
          .then(data => {
              console.log('Task updated:', data);
              // You might want to update the task's attributes here if needed
          })
          .catch(error => console.error('Error updating task:', error));
    }

    // SSE for real-time updates
    const eventSource = new EventSource('/events');

    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.type === 'task_moved') {
            const task = document.getElementById(`task-${data.task_id}`);
            const newColumn = document.getElementById(`column-${data.new_column_id}`);
            if (task && newColumn) {
                newColumn.querySelector('.tasks').appendChild(task);
            }
        } else if (data.type === 'task_added') {
            const column = document.getElementById(`column-${data.column_id}`);
            if (column) {
                const tasksContainer = column.querySelector('.tasks');
                tasksContainer.insertAdjacentHTML('beforeend', data.task_html);
                const newTask = tasksContainer.lastElementChild;
                newTask.addEventListener('dragstart', dragStart);
                newTask.addEventListener('dragend', dragEnd);
            }
        }
    };
}

document.addEventListener('DOMContentLoaded', initKanban);

// Fallback in case DOMContentLoaded has already fired
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initKanban);
} else {
    initKanban();
}