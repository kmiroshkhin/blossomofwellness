import os
from contextlib import contextmanager
from datetime import date
from typing import Optional

from nicegui import ui
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

PRIMARY = 'emerald'

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL is not set.')

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

current_client: Optional[dict] = None
admin_session = False


@contextmanager
def get_conn():
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()


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
        returning id, client_id, check_in_date, weight, energy_level
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


def search_clients(query: str = '') -> list[dict]:
    if query.strip():
        sql = text("""
            select id, name, email
            from public.clients
            where name ilike :query
            order by id desc
            limit 25
        """)
        params = {'query': f'%{query.strip()}%'}
    else:
        sql = text("""
            select id, name, email
            from public.clients
            order by id desc
            limit 25
        """)
        params = {}

    with get_conn() as conn:
        rows = conn.execute(sql, params).mappings().all()
        return [dict(row) for row in rows]


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

    with ui.row().classes('w-full gap-6'):    
        for title, route in [
            ('Client Login', '/client-login'),
            ('Client Sign Up', '/client-signup'),
            ('Admin Login', '/admin-dashboard'),
]:
            ui.button(title, on_click=lambda r=route: ui.navigate.to(r)).classes('w-full')


@ui.page('/client-login')
def client_login_page():
    global current_client

    page_shell('Client Login', 'Enter your email', '/')

    email = ui.input('Email').classes('w-full')

    def login():
        global current_client
        client = get_client_by_email(email.value or '')
        if not client:
            ui.notify('Client not found', type='negative')
            return
        current_client = client
        ui.navigate.to('/client-checkin')

    ui.button('Login', on_click=login)


@ui.page('/client-signup')
def client_signup_page():
    global current_client

    page_shell('Sign Up', 'Create a client profile', '/')

    name = ui.input('Name')
    email = ui.input('Email')

    def signup():
        global current_client
        if not name.value or not email.value:
            ui.notify('Name and email required', type='warning')
            return
        client = create_client_record(name.value, email.value)
        current_client = client
        ui.navigate.to('/client-checkin')

    ui.button('Create', on_click=signup)


@ui.page('/client-checkin')
def client_checkin_page():
    page_shell('Check-in', 'Submit today’s data', '/')

    weight = ui.input('Weight')
    energy = ui.input('Energy (1–10)')
    sleep = ui.input('Sleep')
    workout = ui.input('Workout')
    note = ui.textarea('Note')

    def submit():
        if not current_client:
            ui.notify('Login required', type='negative')
            return
        submit_checkin_record(
            current_client['id'],
            weight.value,
            energy.value,
            sleep.value,
            workout.value,
            note.value,
        )
        ui.notify('Saved')

    ui.button('Submit', on_click=submit)


@ui.page('/admin-dashboard')
def admin_dashboard_page():
    page_shell('Admin Dashboard', 'Client overview', '/')

    for client in search_clients():
        ui.label(client['name'])


ui.run(
    host='0.0.0.0',
    port=int(os.environ.get('PORT', 8080)),
    title='Blossom of Wellness',
    reload=False,
)