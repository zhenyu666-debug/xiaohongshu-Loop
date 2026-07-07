import json, sys, urllib.error, urllib.request

BASE = 'http://127.0.0.1:8080'

def post(path, body, headers=None):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(BASE+path, data=data, method='POST',
        headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, json.loads(r.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as e:
        b = e.read().decode('utf-8', errors='replace')
        try: return e.code, json.loads(b)
        except: return e.code, b
    except Exception as e:
        return 0, f'{type(e).__name__}: {e}'

def get(path, headers=None):
    req = urllib.request.Request(BASE+path, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, json.loads(r.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as e:
        b = e.read().decode('utf-8', errors='replace')
        try: return e.code, json.loads(b)
        except: return e.code, b
    except Exception as e:
        return 0, f'{type(e).__name__}: {e}'

def main():
    print('--- auth smoke ---')
    code, body = get('/api/healthz')
    print(f'GET /healthz -> {code} {body!r}')
    if code != 200:
        print('FAIL: backend not healthy'); return 1

    email, pwd = 'smoke@mgu.local', 'smoke12345'

    code, body = post('/api/auth/signup', {
        'email': email, 'password': pwd, 'display_name': 'smoke', 'tenant_name': 'smoke-tnt'
    })
    print(f'POST /auth/signup -> {code} {body!r}')
    if code not in (200, 201, 409):
        print('FAIL: signup'); return 1

    code, body = post('/api/auth/login', {'email': email, 'password': pwd})
    print(f'POST /auth/login -> {code} {body!r}')
    if code != 200:
        print('FAIL: login'); return 1
    if not isinstance(body, dict) or 'user_id' not in body:
        print('FAIL: login no user_id'); return 1

    code, body = get('/api/auth/me')
    print(f'GET /auth/me (no token) -> {code}')
    print('OK')
    return 0

if __name__ == '__main__':
    sys.exit(main())
