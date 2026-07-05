#!/usr/bin/env python3
"""Test harness for Flask API assessment"""

import requests
import json
import sys

BASE_URL = 'http://localhost:5000'

total_tests = 0
passed_tests = 0
test_results = []


def run_test(name, fn):
    global total_tests, passed_tests
    total_tests += 1
    try:
        fn()
        passed_tests += 1
        test_results.append({'name': name, 'passed': True})
    except Exception as e:
        test_results.append({'name': name, 'passed': False, 'error': str(e)})


def test_get_items():
    res = requests.get(f'{BASE_URL}/api/items')
    assert res.status_code == 200, f'Expected 200, got {res.status_code}'
    assert isinstance(res.json(), list), 'Expected array response'


def test_create_item():
    res = requests.post(f'{BASE_URL}/api/items', json={'name': 'Test Item'})
    assert res.status_code == 201, f'Expected 201, got {res.status_code}'
    assert 'id' in res.json(), 'Expected id in response'


def test_get_item_by_id():
    create_res = requests.post(f'{BASE_URL}/api/items', json={'name': 'Get Test'})
    item_id = create_res.json().get('id')
    res = requests.get(f'{BASE_URL}/api/items/{item_id}')
    assert res.status_code == 200, f'Expected 200, got {res.status_code}'


def test_update_item():
    create_res = requests.post(f'{BASE_URL}/api/items', json={'name': 'Update Test'})
    item_id = create_res.json().get('id')
    res = requests.put(f'{BASE_URL}/api/items/{item_id}', json={'name': 'Updated'})
    assert res.status_code == 200, f'Expected 200, got {res.status_code}'


def test_delete_item():
    create_res = requests.post(f'{BASE_URL}/api/items', json={'name': 'Delete Test'})
    item_id = create_res.json().get('id')
    res = requests.delete(f'{BASE_URL}/api/items/{item_id}')
    assert res.status_code in [200, 204], f'Expected 200/204, got {res.status_code}'


if __name__ == '__main__':
    print('Running tests...\n')

    run_test('GET /api/items returns 200 array', test_get_items)
    run_test('POST /api/items creates item', test_create_item)
    run_test('GET /api/items/:id returns item', test_get_item_by_id)
    run_test('PUT /api/items/:id updates item', test_update_item)
    run_test('DELETE /api/items/:id deletes item', test_delete_item)

    score = round((passed_tests / total_tests) * 100) if total_tests > 0 else 0
    result = {
        'score': score,
        'max_score': 100,
        'passed': passed_tests,
        'total': total_tests,
        'test_results': test_results,
    }

    print(f'\nScore: {score}/100 ({passed_tests}/{total_tests} tests passed)\n')
    print(json.dumps(result, indent=2))