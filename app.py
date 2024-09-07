from flask import Flask, request, jsonify, render_template, Response
from flask_sqlalchemy import SQLAlchemy
from queue import Queue
import json
import time
import logging

logging.basicConfig(level=logging.DEBUG)

db = SQLAlchemy()
event_queue = Queue()

class Board(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    columns = db.relationship('Column', backref='board', lazy=True, cascade='all, delete-orphan')

class Column(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    board_id = db.Column(db.Integer, db.ForeignKey('board.id'), nullable=False)
    tasks = db.relationship('Task', backref='column', lazy=True, cascade='all, delete-orphan')

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    order = db.Column(db.Integer, nullable=False)
    column_id = db.Column(db.Integer, db.ForeignKey('column.id'), nullable=False)

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kanban.db'
    db.init_app(app)

    with app.app_context():
        db.create_all()
        create_sample_data()  # Add this line

    @app.route('/boards', methods=['GET', 'POST'])
    def handle_boards():
        if request.method == 'GET':
            boards = Board.query.all()
            return render_template('index.html', boards=boards)
        elif request.method == 'POST':
            data = request.form
            new_board = Board(name=data['name'])
            db.session.add(new_board)
            db.session.commit()
            return render_template('board_item.html', board=new_board)

    @app.route('/boards/<int:board_id>', methods=['GET', 'PUT', 'DELETE'])
    def handle_board(board_id):
        board = Board.query.get_or_404(board_id)
        if request.method == 'GET':
            logging.debug(f"Rendering board {board_id} with {len(board.columns)} columns and {sum(len(column.tasks) for column in board.columns)} tasks")
            return render_template('board.html', board=board)
        elif request.method == 'PUT':
            data = request.json
            board.name = data['name']
            db.session.commit()
            return jsonify({'id': board.id, 'name': board.name})
        elif request.method == 'DELETE':
            db.session.delete(board)
            db.session.commit()
            return '', 204

    @app.route('/boards/<int:board_id>/columns', methods=['POST'])
    def create_column(board_id):
        board = Board.query.get_or_404(board_id)
        data = request.form
        new_column = Column(name=data['name'], order=len(board.columns), board_id=board.id)
        db.session.add(new_column)
        db.session.commit()
        return render_template('column.html', column=new_column)

    @app.route('/columns/<int:column_id>', methods=['PUT', 'DELETE'])
    def handle_column(column_id):
        column = Column.query.get_or_404(column_id)
        if request.method == 'PUT':
            data = request.json
            column.name = data['name']
            column.order = data['order']
            db.session.commit()
            return jsonify({'id': column.id, 'name': column.name, 'order': column.order})
        elif request.method == 'DELETE':
            db.session.delete(column)
            db.session.commit()
            return '', 204

    @app.route('/columns/<int:column_id>/tasks', methods=['POST'])
    def create_task(column_id):
        column = Column.query.get_or_404(column_id)
        data = request.form
        new_task = Task(title=data['title'], description=data.get('description', ''), order=len(column.tasks), column_id=column.id)
        db.session.add(new_task)
        db.session.commit()

        if request.headers.get('HX-Request') == 'true':
            # If it's an HTMX request, return the task HTML directly
            return render_template('task.html', task=new_task)
        else:
            # If it's not an HTMX request, send an SSE event
            event_queue.put({
                'type': 'task_added',
                'column_id': column.id,
                'task_html': render_template('task.html', task=new_task)
            })
            return '', 204  # No content response

    @app.route('/tasks/<int:task_id>', methods=['PUT', 'DELETE'])
    def handle_task(task_id):
        task = Task.query.get_or_404(task_id)
        if request.method == 'PUT':
            data = request.json
            if 'column_id' in data:
                task.column_id = data['column_id']
            if 'order' in data:
                task.order = data['order']
            db.session.commit()
            return jsonify({'id': task.id, 'column_id': task.column_id, 'order': task.order})
        elif request.method == 'DELETE':
            db.session.delete(task)
            db.session.commit()
            return '', 204

    @app.route('/')
    def index():
        boards = Board.query.all()
        return render_template('index.html', boards=boards)

    @app.route('/boards/<int:board_id>')
    def view_board(board_id):
        board = Board.query.get_or_404(board_id)
        logging.debug(f"Rendering board {board_id} with {len(board.columns)} columns and {sum(len(column.tasks) for column in board.columns)} tasks")
        return render_template('board.html', board=board)

    @app.route('/events')
    def sse():
        def event_stream():
            while True:
                if not event_queue.empty():
                    event = event_queue.get()
                    yield f"data: {json.dumps(event)}\n\n"
                time.sleep(0.1)

        return Response(event_stream(), content_type='text/event-stream')

    return app

def create_sample_data():
    # Check if we already have data
    if Board.query.first() is not None:
        return

    # Create a sample board
    board = Board(name="Sample Board")
    db.session.add(board)
    
    # Create sample columns
    columns = [
        Column(name="To Do", order=0, board=board),
        Column(name="In Progress", order=1, board=board),
        Column(name="Done", order=2, board=board)
    ]
    db.session.add_all(columns)
    
    # Create sample tasks
    tasks = [
        Task(title="Task 1", description="Description for Task 1", order=0, column=columns[0]),
        Task(title="Task 2", description="Description for Task 2", order=1, column=columns[0]),
        Task(title="Task 3", description="Description for Task 3", order=0, column=columns[1]),
    ]
    db.session.add_all(tasks)
    
    db.session.commit()
    logging.info("Sample data created successfully")

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)