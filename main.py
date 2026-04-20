import os
from contextlib import contextmanager
from datetime import date
from typing import Optional

from nicegui import ui
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Blossom of Wellness - NiceGUI + direct Postgres version
#
# Install:
#   pip install nicegui sqlalchemy psycopg2-binary
#
# Run:
#   python main.py
#
# Recommended:
#   set DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.jajnaytwazztzywgtkyp.supabase.co:5432/postgres
#
# For current local testing, a fallback connection string is included below.

PRIMARY = 'emerald'

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://postgres:Itisabeautifulday@db.jajnaytwazztzywgtkyp.supabase.co:5432/postgres',
)

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


# -----------------------------
# Data access helpers
# -----------------------------
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
            raise RuntimeError('Client insert returned no data.')
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
        'workout_completed': workout_completed if workout_completed else None,
        'quick_note': quick_note if quick_note else None,
    }
    with get_conn() as conn:
        row = conn.execute(sql, payload).mappings().first()
        conn.commit()
        if not row:
            raise RuntimeError('Check-in insert returned no data.')
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
            client_id,
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
        return True, 'Database connected successfully.'
    except SQLAlchemyError as exc:
        return False, f'Database connection failed: {exc}'


# -----------------------------
# Shared layout
# -----------------------------
def page_shell(title: str, subtitle: str, back_route: str | None = None):
    with ui.column().classes('w-full max-w-6xl mx-auto p-6 gap-6'):
        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center gap-3'):
                ui.icon('local_florist', color=PRIMARY).classes('text-4xl')
                with ui.column().classes('gap-0'):
                    ui.label('Blossom of Wellness').classes('text-2xl font-bold')
                    ui.label('Simple check-ins. Visible progress. Human coaching.').classes('text-gray-600')
            if back_route:
                ui.button('Back', on_click=lambda: ui.navigate.to(back_route), icon='arrow_back').props('outline')

        ui.label(title).classes('text-3xl font-bold')
        ui.label(subtitle).classes('text-lg text-gray-700')


@ui.page('/')
def landing_page():
    page_shell(
        'Build the first working front door',
        'This Python shell is now aligned to the real clients and check_ins tables.'
    )

    ok, message = test_db_connection()
    ui.label(message).classes(f"text-sm {'text-green-700' if ok else 'text-red-600'}")

    with ui.row().classes('w-full gap-6 items-stretch'):
        with ui.card().classes('col-grow w-full p-6 rounded-2xl shadow-lg'):
            ui.label('A wellness platform with two clear sides').classes('text-2xl font-semibold')
            ui.label(
                'Clients log in, check in quickly, and review progress. Flor logs in as admin to review trends and coach.'
            ).classes('text-gray-600')

            with ui.row().classes('w-full gap-4 mt-4 items-stretch'):
                for icon, title, body, route in [
                    ('person', 'Client Login', 'Existing clients enter their account and continue daily check-ins.', '/client-login'),
                    ('person_add', 'Client Sign Up', 'New clients create their profile and basic onboarding details.', '/client-signup'),
                    ('verified_user', 'Admin Login', 'Flor reviews clients, trends, and coaching notes from one dashboard.', '/admin-login'),
                ]:
                    with ui.card().classes('p-5 rounded-2xl w-full'):
                        ui.icon(icon, color=PRIMARY).classes('text-3xl')
                        ui.label(title).classes('text-lg font-semibold mt-2')
                        ui.label(body).classes('text-sm text-gray-600')
                        ui.button('Open', on_click=lambda r=route: ui.navigate.to(r)).classes('mt-4 w-full')

        with ui.card().classes('w-full max-w-sm p-6 rounded-2xl shadow-lg'):
            ui.label("Today's continuation").classes('text-xl font-semibold')
            ui.label('Direct Postgres connection and schema-aligned inserts.').classes('text-gray-600')
            for i, item in enumerate([
                'clients table uses id, name, email',
                'check_ins uses check_in_date, weight, energy_level',
                'Missing fields added via SQL migration',
                'Client sign-up creates a real row',
                'Check-in writes a real row',
                'Admin dashboard reads real data',
            ], start=1):
                with ui.row().classes('items-center gap-3 w-full border rounded-xl p-3 mt-3'):
                    ui.avatar(str(i), color='emerald-2', text_color='emerald-10')
                    ui.label(item).classes('text-sm')


@ui.page('/client-login')
def client_login_page():
    global current_client

    page_shell(
        'Client login',
        'For this stage, login resolves a client by email from the clients table.',
        '/'
    )

    with ui.card().classes('w-full max-w-xl mx-auto p-6 rounded-2xl shadow-lg'):
        ui.label('Welcome back').classes('text-2xl font-semibold')
        ui.label('Enter your email to load your profile.').classes('text-gray-600')
        email = ui.input('Email', placeholder='client@email.com').classes('w-full mt-4')

        def login_client():
            global current_client
            try:
                client = get_client_by_email(email.value or '')
                if not client:
                    ui.notify('No client found with that email.', type='negative')
                    return
                current_client = client
                ui.notify(f"Welcome back, {client.get('name', 'client')}")
                ui.navigate.to('/client-checkin')
            except Exception as exc:
                ui.notify(f'Client login error: {exc}', type='negative')

        ui.button('Enter client portal', on_click=login_client).classes('w-full mt-4')


@ui.page('/client-signup')
def client_signup_page():
    global current_client

    page_shell(
        'Client sign up',
        'This writes a real row to public.clients using the confirmed schema.',
        '/'
    )

    with ui.card().classes('w-full max-w-2xl mx-auto p-6 rounded-2xl shadow-lg'):
        ui.label('New client intake').classes('text-2xl font-semibold')
        ui.label('Keep this light. The goal is to get a client into the system without friction.').classes('text-gray-600')
        with ui.row().classes('w-full gap-4 mt-4'):
            full_name = ui.input('Full name', placeholder='Client name').classes('w-full')
            email = ui.input('Email', placeholder='client@email.com').classes('w-full')

        def signup_client():
            global current_client
            try:
                if not full_name.value or not email.value:
                    ui.notify('Name and email are required.', type='warning')
                    return
                existing = get_client_by_email(email.value)
                if existing:
                    current_client = existing
                    ui.notify('That email already exists. Loading existing client profile instead.', type='warning')
                    ui.navigate.to('/client-checkin')
                    return
                client = create_client_record(name=full_name.value, email=email.value)
                current_client = client
                ui.notify('Client account created successfully.')
                ui.navigate.to('/client-checkin')
            except Exception as exc:
                ui.notify(f'Client sign-up error: {exc}', type='negative')

        ui.button('Create client account', on_click=signup_client).classes('w-full mt-4')


@ui.page('/client-checkin')
def client_checkin_page():
    page_shell(
        'Daily check-in',
        'This writes directly into public.check_ins with the aligned column names.',
        '/'
    )

    with ui.row().classes('w-full gap-6 items-start'):
        with ui.card().classes('w-full p-6 rounded-2xl shadow-lg'):
            ui.label("Today's stats").classes('text-2xl font-semibold')
            if current_client:
                ui.label(f"Current client: {current_client.get('name', 'Unknown')}").classes('text-sm text-gray-600')
            else:
                ui.label('No active client session loaded. Login or sign up first.').classes('text-sm text-red-600')

            weight = ui.input('Weight', placeholder='e.g. 184.2').classes('w-full mt-4')
            energy_level = ui.input('Energy level (1-10)', placeholder='e.g. 7').classes('w-full')
            sleep_hours = ui.input('Sleep hours', placeholder='e.g. 7.5').classes('w-full')
            workout_completed = ui.input('Workout completed?', placeholder='Yes / No').classes('w-full')
            quick_note = ui.textarea('Quick note', placeholder='How are you feeling today?').classes('w-full')

            def submit_checkin():
                try:
                    if not current_client:
                        ui.notify('No active client. Please login first.', type='negative')
                        return
                    submit_checkin_record(
                        client_id=current_client['id'],
                        weight=weight.value or '',
                        energy_level=energy_level.value or '',
                        sleep_hours=sleep_hours.value or '',
                        workout_completed=workout_completed.value or '',
                        quick_note=quick_note.value or '',
                    )
                    ui.notify('Check-in submitted successfully.')
                    weight.set_value('')
                    energy_level.set_value('')
                    sleep_hours.set_value('')
                    workout_completed.set_value('')
                    quick_note.set_value('')
                    recent_checkins.refresh()
                except Exception as exc:
                    ui.notify(f'Check-in submission error: {exc}', type='negative')

            ui.button('Submit check-in', on_click=submit_checkin).classes('w-full mt-4')

        with ui.card().classes('w-full max-w-md p-6 rounded-2xl shadow-lg'):
            ui.label('Recent check-ins').classes('text-xl font-semibold')

            @ui.refreshable
            def recent_checkins():
                if not current_client:
                    ui.label('Login required before loading history.').classes('text-sm text-gray-600')
                    return
                try:
                    rows = get_recent_checkins_for_client(current_client['id'])
                    if not rows:
                        ui.label('No check-ins yet.').classes('text-sm text-gray-600')
                        return
                    for row in rows:
                        with ui.card().classes('w-full p-3 rounded-xl bg-gray-50 shadow-none mt-2'):
                            ui.label(str(row.get('check_in_date', ''))).classes('text-xs text-gray-500')
                            ui.label(f"Weight: {row.get('weight', '-')}")
                            ui.label(f"Energy: {row.get('energy_level', '-')}")
                            ui.label(f"Sleep: {row.get('sleep_hours', '-')}")
                            ui.label(f"Workout: {row.get('workout_completed', '-')}")
                            ui.label(f"Note: {row.get('quick_note', '')}").classes('text-sm text-gray-700')
                except Exception as exc:
                    ui.label(f'Could not load check-ins: {exc}').classes('text-sm text-red-600')

            recent_checkins()


@ui.page('/admin-login')
def admin_login_page():
    global admin_session

    page_shell(
        'Admin login',
        'This keeps admin separate from the client flow while we validate the data path.',
        '/'
    )

    with ui.card().classes('w-full max-w-xl mx-auto p-6 rounded-2xl shadow-lg'):
        ui.label('Admin access').classes('text-2xl font-semibold')
        ui.label('This placeholder login opens the dashboard so we can validate the workflow first.').classes('text-gray-600')
        ui.input('Email', placeholder='admin@blossomofwellness.fit').classes('w-full mt-4')
        ui.input('Password', password=True, password_toggle_button=True).classes('w-full')

        def login_admin():
            global admin_session
            admin_session = True
            ui.navigate.to('/admin-dashboard')

        ui.button('Enter admin dashboard', on_click=login_admin).classes('w-full mt-4')


@ui.page('/admin-dashboard')
def admin_dashboard_page():
    page_shell(
        'Flor admin dashboard',
        'This reads real client rows and their latest check-ins from Postgres.',
        '/'
    )

    search_input = ui.input('Search client by name', placeholder='Type a client name...').classes('w-full')
    results_container = ui.column().classes('w-full gap-3')

    def render_clients(query: str = ''):
        results_container.clear()
        try:
            clients = search_clients(query)
            with results_container:
                if not clients:
                    ui.label('No clients found.').classes('text-sm text-gray-600')
                    return
                for client in clients:
                    client_id = client.get('id')
                    recent = get_recent_checkins_for_client(client_id, limit=1) if client_id else []
                    last = recent[0] if recent else {}
                    with ui.card().classes('w-full p-4 rounded-2xl shadow-sm'):
                        with ui.row().classes('w-full items-center justify-between'):
                            with ui.column().classes('gap-0'):
                                ui.label(client.get('name', 'Unknown')).classes('text-lg font-semibold')
                                ui.label(client.get('email', '')).classes('text-sm text-gray-600')
                            if last:
                                ui.badge(f"Last check-in: {last.get('check_in_date', '')}")
                            else:
                                ui.badge('No check-ins yet')
                        ui.label(f"Latest weight: {last.get('weight', '—')}").classes('mt-2 text-sm text-gray-700')
                        ui.label(f"Latest energy: {last.get('energy_level', '—')}").classes('text-sm text-gray-700')
                        ui.label(f"Latest note: {last.get('quick_note', '—')}").classes('text-sm text-gray-700')
        except Exception as exc:
            with results_container:
                ui.label(f'Could not load clients: {exc}').classes('text-sm text-red-600')

    search_input.on('update:model-value', lambda e: render_clients(e.args))
    render_clients()


ui.run(title='Blossom of Wellness', reload=False)