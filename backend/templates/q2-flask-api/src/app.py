from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

items = []


@app.route('/api/items', methods=['GET'])
def get_items():
    return jsonify(items)


@app.route('/api/items', methods=['POST'])
def create_item():
    # TODO: Implement create item
    return jsonify({'message': 'Not implemented'}), 201


@app.route('/api/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    # TODO: Implement get item by id
    return jsonify({'message': 'Not implemented'}), 404


@app.route('/api/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    # TODO: Implement update item
    return jsonify({'message': 'Not implemented'}), 404


@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    # TODO: Implement delete item
    return jsonify({'message': 'Not implemented'}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)