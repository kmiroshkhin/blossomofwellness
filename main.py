import os
from contextlib import contextmanager
from datetime import date
from typing import Optional

from nicegui import app, ui
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


PRIMARY = 'emerald'

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL is not set.')

ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
if not ADMIN_EMAIL or not ADMIN_PASSWORD:
    raise RuntimeError('ADMIN_EMAIL and ADMIN_PASSWORD must be set.')

STORAGE_SECRET = os.getenv('STORAGE_SECRET')
if not STORAGE_SECRET:
    raise RuntimeError('STORAGE_SECRET must be set.')

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


@contextmanager
def get_conn():
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()


def get_client_session() -> Optional[dict]:
    return app.storage.user.get('client')


def set_client_session(client: dict) -> None:
    app.storage.user['client'] = client


def clear_client_session() -> None:
    app.storage.user.pop('client', None)


def is_admin_logged_in() -> bool:
    return bool(app.storage.user.get('is_admin', False))


def set_admin_logged_in(value: bool) -> None:
    app.storage.user['is_admin'] = value


def create_client_record(name: str, email: str) -> dict:
    sql = text("""
        insert into public.clients (name, email)
        values (:name, :email)
        returning id, name, email
    """)
    with get_conn() as conn:
        row = conn.execute(sql, {'name': name, 'email': email}).mappings().first()
        conn.commit()
        if not row:
            raise RuntimeError('Client insert failed.')
        return dict(row)


def get_client_by_email(email: str) -> Optional[dict]:
    sql = text("""
        select id, name, email
        from public.clients
        where lower(email) = lower(:email)
        limit 1
    """)
    with get_conn() as conn:
        row = conn.execute(sql, {'email': email}).mappings().first()
        return dict(row) if row else None


def submit_checkin_record(
    client_id: int,
    weight: str,
    energy_level: str,
    sleep_hours: str = '',
    workout_completed: str = '',
    quick_note: str = '',
) -> dict:
    sql = text("""
        insert into public.check_ins (
            client_id,
            check_in_date,
            weight,
            energy_level,
            sleep_hours,
            workout_completed,
            quick_note
        )
        values (
            :client_id,
            :check_in_date,
            :weight,
            :energy_level,
            :sleep_hours,
            :workout_completed,
            :quick_note
        )
        returning id, client_id, check_in_date, weight, energy_level, sleep_hours, workout_completed, quick_note
    """)

    payload = {
        'client_id': client_id,
        'check_in_date': date.today().isoformat(),
        'weight': float(weight) if weight else None,
        'energy_level': int(energy_level) if energy_level else None,
        'sleep_hours': float(sleep_hours) if sleep_hours else None,
        'workout_completed': workout_completed or None,
        'quick_note': quick_note or None,
    }

    with get_conn() as conn:
        row = conn.execute(sql, payload).mappings().first()
        conn.commit()
        if not row:
            raise RuntimeError('Check-in insert failed.')
        return dict(row)


def get_recent_checkins_for_client(client_id: int, limit: int = 10) -> list[dict]:
    sql = text("""
        select
            id,
            check_in_date,
            weight,
            energy_level,
            sleep_hours,
            workout_completed,
            quick_note
        from public.check_ins
        where client_id = :client_id
        order by check_in_date desc, id desc
        limit :limit
    """)
    with get_conn() as conn:
        rows = conn.execute(sql, {'client_id': client_id, 'limit': limit}).mappings().all()
        return [dict(row) for row in rows]


def get_admin_overview(limit_clients: int = 100) -> list[dict]:
    sql = text("""
        select
            c.id,
            c.name,
            c.email,
            ci.check_in_date,
            ci.weight,
            ci.energy_level,
            ci.sleep_hours,
            ci.workout_completed,
            ci.quick_note
        from public.clients c
        left join (
            select distinct on (client_id)
                client_id,
                check_in_date,
                weight,
                energy_level,
                sleep_hours,
                workout_completed,
                quick_note
            from public.check_ins
            order by client_id, check_in_date desc, id desc
        ) ci
            on c.id = ci.client_id
        order by c.id desc
        limit :limit_clients
    """)
    with get_conn() as conn:
        rows = conn.execute(sql, {'limit_clients': limit_clients}).mappings().all()
        return [dict(row) for row in rows]


def test_db_connection() -> tuple[bool, str]:
    try:
        with get_conn() as conn:
            conn.execute(text('select 1'))
        return True, 'Database connected.'
    except SQLAlchemyError as exc:
        return False, f'Connection failed: {exc}'


def page_shell(title: str, subtitle: str, back_route: str | None = None):
    with ui.column().classes('w-full max-w-6xl mx-auto p-6 gap-6'):
        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center gap-3'):
                ui.icon('local_florist', color=PRIMARY).classes('text-4xl')
                with ui.column().classes('gap-0'):
                    ui.label('Blossom of Wellness').classes('text-2xl font-bold')
                    ui.label('Daily check-ins and coaching').classes('text-gray-600')
            if back_route:
                ui.button('Back', on_click=lambda: ui.navigate.to(back_route), icon='arrow_back').props('outline')

        ui.label(title).classes('text-3xl font-bold')
        ui.label(subtitle).classes('text-lg text-gray-700')


@ui.page('/')
def landing_page():
    page_shell('Welcome', 'Client check-ins and admin review')

    ok, message = test_db_connection()
    ui.label(message).classes(f"text-sm {'text-green-700' if ok else 'text-red-600'}")

    with ui.column().classes('w-full gap-4'):
        ui.button('Client Login', on_click=lambda: ui.navigate.to('/client-login')).classes('w-full')
        ui.button('Client Sign Up', on_click=lambda: ui.navigate.to('/client-signup')).classes('w-full')
        ui.button('Admin Login', on_click=lambda: ui.navigate.to('/admin-login')).classes('w-full')


@ui.page('/client-signup')
def client_signup_page():
    page_shell('Client Sign Up', 'Enter name and email to create a client record', '/')

    name = ui.input('Name').classes('w-full max-w-lg')
    email = ui.input('Email').classes('w-full max-w-lg')

    def signup():
        try:
            if not name.value or not email.value:
                ui.notify('Name and email required', type='warning')
                return

            existing = get_client_by_email(email.value)
            if existing:
                ui.notify('Client already exists. Please use Client Login.', type='warning')
                return

            create_client_record(name.value, email.value)
            ui.navigate.to('/client-signup-success')
        except Exception as exc:
            ui.notify(f'Sign up failed: {exc}', type='negative')

    ui.button('Create Client', on_click=signup).classes('w-full max-w-lg')


@ui.page('/client-signup-success')
def client_signup_success_page():
    page_shell('Client Created', 'The client was successfully added to the system.', '/')
    ui.label('Success — the client record has been saved.').classes('text-lg text-green-700')
    ui.button('Back to Home', on_click=lambda: ui.navigate.to('/')).classes('mt-4')


@ui.page('/client-login')
def client_login_page():
    page_shell('Client Login', 'Enter your email to continue to check-ins', '/')

    email = ui.input('Email').classes('w-full max-w-lg')

    def login():
        try:
            client = get_client_by_email(email.value or '')
            if not client:
                ui.notify('Client not found', type='negative')
                return
            set_client_session(client)
            ui.navigate.to('/client-checkin')
        except Exception as exc:
            ui.notify(f'Login failed: {exc}', type='negative')

    ui.button('Login', on_click=login).classes('w-full max-w-lg')


@ui.page('/client-checkin')
def client_checkin_page():
    client = get_client_session()
    if not client:
        ui.navigate.to('/client-login')
        return

    page_shell('Client Check-In', f"Logged in as {client['name']}", '/')

    with ui.column().classes('w-full max-w-xl gap-3'):
        weight = ui.input('Weight')
        energy = ui.input('Energy (1–10)')
        sleep = ui.input('Sleep Hours')
        workout = ui.input('Workout Completed?')
        note = ui.textarea('Note')

        def submit():
            try:
                if not energy.value:
                    ui.notify('Energy is required', type='warning')
                    return

                submit_checkin_record(
                    client['id'],
                    weight.value,
                    energy.value,
                    sleep.value,
                    workout.value,
                    note.value,
                )
                ui.notify('Check-in saved')
                recent.refresh()
            except Exception as exc:
                ui.notify(f'Check-in failed: {exc}', type='negative')

        ui.button('Submit Check-In', on_click=submit).classes('w-full')
        ui.button('Log Out', on_click=lambda: (clear_client_session(), ui.navigate.to('/'))).props('outline')

    ui.separator()
    ui.label('Recent Check-Ins').classes('text-xl font-semibold')

    @ui.refreshable
    def recent():
        rows = get_recent_checkins_for_client(client['id'], limit=10)
        if not rows:
            ui.label('No check-ins yet.')
            return

        for row in rows:
            with ui.card().classes('w-full max-w-xl p-4'):
                ui.label(f"Date: {row.get('check_in_date', '')}")
                ui.label(f"Weight: {row.get('weight', '—')}")
                ui.label(f"Energy: {row.get('energy_level', '—')}")
                ui.label(f"Sleep: {row.get('sleep_hours', '—')}")
                ui.label(f"Workout: {row.get('workout_completed', '—')}")
                ui.label(f"Note: {row.get('quick_note', '—')}")

    recent()


@ui.page('/admin-login')
def admin_login_page():
    if is_admin_logged_in():
        ui.navigate.to('/admin-dashboard')
        return

    page_shell('Admin Login', 'Enter admin credentials', '/')

    email = ui.input('Admin Email').classes('w-full max-w-lg')
    password = ui.input('Password', password=True, password_toggle_button=True).classes('w-full max-w-lg')

    def login():
        if email.value == ADMIN_EMAIL and password.value == ADMIN_PASSWORD:
            set_admin_logged_in(True)
            ui.navigate.to('/admin-dashboard')
        else:
            ui.notify('Invalid admin credentials', type='negative')

    ui.button('Login', on_click=login).classes('w-full max-w-lg')


@ui.page('/admin-dashboard')
def admin_dashboard_page():
    if not is_admin_logged_in():
        ui.navigate.to('/admin-login')
        return

    page_shell('Admin Dashboard', 'Existing clients and latest records', '/')

    with ui.row().classes('w-full items-center gap-4'):
        search = ui.input('Search clients by name or email').classes('w-full max-w-lg')

        def logout():
            set_admin_logged_in(False)
            ui.navigate.to('/')

        ui.button('Log Out', on_click=logout).props('outline')

    results = ui.column().classes('w-full gap-3')

    def render(query: str = ''):
        results.clear()
        rows = get_admin_overview()

        if query.strip():
            q = query.strip().lower()
            rows = [
                row for row in rows
                if q in (row.get('name') or '').lower() or q in (row.get('email') or '').lower()
            ]

        with results:
            if not rows:
                ui.label('No matching clients found.')
                return

            for row in rows:
                with ui.card().classes('w-full p-4'):
                    ui.label(row.get('name', 'Unknown')).classes('text-lg font-semibold')
                    ui.label(f"Email: {row.get('email', '—')}")
                    ui.label(f"Last check-in: {row.get('check_in_date', 'No check-ins yet')}")
                    ui.label(f"Latest weight: {row.get('weight', '—')}")
                    ui.label(f"Latest energy: {row.get('energy_level', '—')}")
                    ui.label(f"Latest sleep: {row.get('sleep_hours', '—')}")
                    ui.label(f"Latest workout: {row.get('workout_completed', '—')}")
                    ui.label(f"Latest note: {row.get('quick_note', '—')}")

    search.on('update:model-value', lambda e: render(e.args))
    render()


ui.run(
    host='0.0.0.0',
    port=int(os.environ.get('PORT', 8080)),
    title='Blossom of Wellness',
    reload=False,
    storage_secret=STORAGE_SECRET,
)