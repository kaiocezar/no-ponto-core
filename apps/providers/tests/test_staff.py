"""
Testes BDD — Staff: CRUD, permissões, invite flow, endpoint público.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.providers.models import ServiceStaff, Staff
from apps.providers.tests.factories import (
    ProviderProfileFactory,
    StaffFactory,
    StaffInviteFactory,
)
from apps.services.tests.factories import ServiceFactory

STAFF_LIST_URL = "/api/v1/providers/me/staff/"
ACCEPT_INVITE_VALIDATE_URL = "/api/v1/accounts/accept-invite/"
ACCEPT_INVITE_URL = "/api/v1/accounts/accept-invite/accept/"


def staff_detail_url(pk: object) -> str:
    return f"/api/v1/providers/me/staff/{pk}/"


def resend_url(pk: object) -> str:
    return f"/api/v1/providers/me/staff/{pk}/resend-invite/"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def provider_profile(db):
    return ProviderProfileFactory()


@pytest.fixture
def owner_staff(provider_profile):
    """Staff com role=owner vinculado ao provider_profile."""
    return StaffFactory(provider=provider_profile, user=provider_profile.user, role="owner")


@pytest.fixture
def authenticated_owner(provider_profile, owner_staff):
    client = APIClient()
    client.force_authenticate(user=provider_profile.user)
    return client


@pytest.fixture
def manager_user(db):
    return User.objects.create_user(
        email="manager@test.com",
        password="senha_segura_123",
        full_name="Manager Teste",
        role=User.Role.PROVIDER,
        auth_provider=User.AuthProvider.EMAIL,
    )


@pytest.fixture
def manager_staff(provider_profile, manager_user):
    return StaffFactory(provider=provider_profile, user=manager_user, role="manager")


@pytest.fixture
def authenticated_manager(provider_profile, manager_staff):
    client = APIClient()
    client.force_authenticate(user=manager_staff.user)
    return client


@pytest.fixture
def practitioner_user(db):
    return User.objects.create_user(
        email="pract@test.com",
        password="senha_segura_123",
        full_name="Profissional Teste",
        role=User.Role.PROVIDER,
        auth_provider=User.AuthProvider.EMAIL,
    )


@pytest.fixture
def practitioner_staff(provider_profile, practitioner_user):
    return StaffFactory(provider=provider_profile, user=practitioner_user, role="practitioner")


@pytest.fixture
def authenticated_practitioner(provider_profile, practitioner_staff):
    client = APIClient()
    client.force_authenticate(user=practitioner_staff.user)
    return client


# ── Listar Staff ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestStaffList:
    def test_owner_can_list_staff(self, authenticated_owner: APIClient, owner_staff: Staff) -> None:
        """
        Scenario: Dono lista equipe
          Given prestador autenticado como owner
          When GET /providers/me/staff/
          Then 200 com lista de membros
        """
        resp = authenticated_owner.get(STAFF_LIST_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()) >= 1

    def test_unauthenticated_returns_401(self) -> None:
        resp = APIClient().get(STAFF_LIST_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_practitioner_returns_403(self, authenticated_practitioner: APIClient) -> None:
        """Practitioner não tem acesso ao painel de staff."""
        resp = authenticated_practitioner.get(STAFF_LIST_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── Convidar Staff ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestStaffInvite:
    def test_owner_invites_staff_returns_201(
        self, authenticated_owner: APIClient, provider_profile: object
    ) -> None:
        """
        Scenario: Convidar novo profissional
          Given prestador autenticado como owner
          When POST /providers/me/staff/ com dados válidos
          Then 201 e Staff criado com invite_token gerado
        """
        with patch("apps.providers.tasks.send_staff_invite_email.delay") as mock_task:
            resp = authenticated_owner.post(
                STAFF_LIST_URL,
                {
                    "name": "Novo Profissional",
                    "invite_email": "novo@test.com",
                    "role": "practitioner",
                },
                format="json",
            )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["invite_email"] == "novo@test.com"
        assert mock_task.called

    def test_practitioner_cannot_invite_returns_403(
        self, authenticated_practitioner: APIClient
    ) -> None:
        """
        Scenario: Practitioner tenta convidar — bloqueado
          Then 403
        """
        resp = authenticated_practitioner.post(
            STAFF_LIST_URL,
            {"name": "X", "invite_email": "x@x.com", "role": "practitioner"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_duplicate_invite_email_returns_400(
        self, authenticated_owner: APIClient, provider_profile: object
    ) -> None:
        """
        Scenario: E-mail de convite duplicado
          Given convite ativo para email@test.com
          When segundo convite para o mesmo e-mail
          Then 400
        """
        StaffInviteFactory(provider=provider_profile, invite_email="dup@test.com")
        with patch("apps.providers.tasks.send_staff_invite_email.delay"):
            resp = authenticated_owner.post(
                STAFF_LIST_URL,
                {"name": "Dup", "invite_email": "dup@test.com", "role": "practitioner"},
                format="json",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ── Editar / Desativar Staff ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestStaffDetail:
    def test_owner_can_patch_staff(
        self, authenticated_owner: APIClient, provider_profile: object, owner_staff: Staff
    ) -> None:
        """
        Scenario: Editar nome de um membro
          Given staff existente
          When PATCH /providers/me/staff/{id}/
          Then 200 e nome atualizado
        """
        pract = StaffFactory(provider=provider_profile, role="practitioner")
        resp = authenticated_owner.patch(
            staff_detail_url(pract.pk),
            {"name": "Novo Nome"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["name"] == "Novo Nome"

    def test_deactivate_staff_without_future_appointments(
        self, authenticated_owner: APIClient, provider_profile: object, owner_staff: Staff
    ) -> None:
        """
        Scenario: Desativar profissional sem agendamentos futuros
          Given practitioner sem agendamentos
          When DELETE /providers/me/staff/{id}/
          Then 204 e is_active=False
        """
        pract = StaffFactory(provider=provider_profile, role="practitioner")
        resp = authenticated_owner.delete(staff_detail_url(pract.pk))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        pract.refresh_from_db()
        assert pract.is_active is False

    def test_cannot_deactivate_owner(
        self, authenticated_owner: APIClient, owner_staff: Staff
    ) -> None:
        """
        Scenario: Owner não pode ser desativado
          When DELETE no staff com role=owner
          Then 400
        """
        resp = authenticated_owner.delete(staff_detail_url(owner_staff.pk))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_deactivate_staff_with_future_appointments_returns_400(
        self,
        authenticated_owner: APIClient,
        provider_profile: object,
        owner_staff: Staff,
        db: None,
    ) -> None:
        """
        Scenario: Não pode desativar profissional com agendamentos futuros
          Given agendamento futuro vinculado ao profissional
          When DELETE
          Then 400 com code STAFF_HAS_FUTURE_APPOINTMENTS
        """
        from apps.appointments.models import Appointment, generate_public_id

        pract = StaffFactory(provider=provider_profile, role="practitioner")
        service = ServiceFactory(provider=provider_profile)
        Appointment.objects.create(
            public_id=generate_public_id(),
            provider=provider_profile,
            service=service,
            staff=pract,
            client=None,
            client_name="Cliente",
            client_phone="+5511999990099",
            client_email="",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
            status=Appointment.Status.CONFIRMED,
            origin=Appointment.Origin.ONLINE,
        )
        resp = authenticated_owner.delete(staff_detail_url(pract.pk))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["code"] == "STAFF_HAS_FUTURE_APPOINTMENTS"


# ── Reenviar Convite ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestResendInvite:
    def test_resend_generates_new_token(
        self, authenticated_owner: APIClient, provider_profile: object, owner_staff: Staff
    ) -> None:
        """
        Scenario: Reenvio de convite gera novo token
          Given convite pendente
          When POST /resend-invite/
          Then novo token gerado e e-mail disparado
        """
        invite = StaffInviteFactory(provider=provider_profile)
        old_token = invite.invite_token

        with patch("apps.providers.tasks.send_staff_invite_email.delay") as mock_task:
            resp = authenticated_owner.post(resend_url(invite.pk))

        assert resp.status_code == status.HTTP_200_OK
        invite.refresh_from_db()
        assert invite.invite_token != old_token
        assert mock_task.called

    def test_resend_accepted_invite_returns_400(
        self, authenticated_owner: APIClient, provider_profile: object, owner_staff: Staff
    ) -> None:
        """
        Scenario: Reenvio de convite já aceito
          Given staff com user vinculado
          When POST /resend-invite/
          Then 400
        """
        accepted = StaffFactory(provider=provider_profile, role="practitioner")
        resp = authenticated_owner.post(resend_url(accepted.pk))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ── Invite Flow ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestInviteFlow:
    """
    Feature: Fluxo de aceite de convite
    Como novo profissional
    Quero aceitar meu convite
    Para me cadastrar na plataforma
    """

    def test_validate_invite_valid_token_returns_200(self, provider_profile: object) -> None:
        """
        Scenario: Token válido retorna dados do convite
          Given convite ativo com token válido
          When GET /accounts/accept-invite/?token=
          Then 200 com dados do convite
        """
        invite = StaffInviteFactory(
            provider=provider_profile,
            invite_expires_at=timezone.now() + timedelta(days=7),
        )
        resp = APIClient().get(f"{ACCEPT_INVITE_VALIDATE_URL}?token={invite.invite_token}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["invite_email"] == invite.invite_email

    def test_validate_invite_expired_token_returns_410(self, provider_profile: object) -> None:
        """
        Scenario: Token expirado
          Given convite com invite_expires_at no passado
          When GET /accept-invite/?token=
          Then 410 GONE
        """
        invite = StaffInviteFactory(
            provider=provider_profile,
            invite_expires_at=timezone.now() - timedelta(days=1),
        )
        resp = APIClient().get(f"{ACCEPT_INVITE_VALIDATE_URL}?token={invite.invite_token}")
        assert resp.status_code == status.HTTP_410_GONE

    def test_validate_invite_invalid_token_returns_404(self) -> None:
        """
        Scenario: Token inexistente
          When GET com token inválido
          Then 404
        """
        resp = APIClient().get(f"{ACCEPT_INVITE_VALIDATE_URL}?token={uuid.uuid4()}")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_accept_invite_creates_new_user_and_links_staff(self, provider_profile: object) -> None:
        """
        Scenario: Aceite de convite cria novo usuário
          Given convite para email não cadastrado
          When POST /accept-invite/accept/ com nome e senha
          Then 200, usuário criado e Staff.user vinculado
        """
        invite = StaffInviteFactory(
            provider=provider_profile,
            invite_email="novo_prof@test.com",
            invite_expires_at=timezone.now() + timedelta(days=7),
        )
        resp = APIClient().post(
            ACCEPT_INVITE_URL,
            {
                "token": str(invite.invite_token),
                "full_name": "Novo Profissional",
                "password": "senha_forte_123",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.json()
        invite.refresh_from_db()
        assert invite.user is not None
        assert invite.invite_token is None

    def test_accept_invite_already_accepted_returns_410(self, provider_profile: object) -> None:
        """
        Scenario: Convite já aceito
          Given Staff.user já vinculado
          When POST /accept-invite/accept/
          Then 410 GONE
        """
        accepted_staff = StaffFactory(provider=provider_profile, role="practitioner")
        token_val = uuid.uuid4()
        accepted_staff.invite_token = token_val
        accepted_staff.save(update_fields=["invite_token"])
        resp = APIClient().post(
            ACCEPT_INVITE_URL,
            {
                "token": str(token_val),
                "full_name": "X",
                "password": "senha1234",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_410_GONE

    def test_accept_invite_with_authenticated_user(self, provider_profile: object) -> None:
        """
        Scenario: Aceite com usuário já autenticado
          Given usuário logado
          When POST com token válido
          Then Staff vinculado ao usuário existente
        """
        invite = StaffInviteFactory(
            provider=provider_profile,
            invite_expires_at=timezone.now() + timedelta(days=7),
        )
        existing_user = User.objects.create_user(
            email="already@test.com",
            password="senha_segura",
            full_name="Já Cadastrado",
            role=User.Role.PROVIDER,
            auth_provider=User.AuthProvider.EMAIL,
        )
        api_client = APIClient()
        api_client.force_authenticate(user=existing_user)
        resp = api_client.post(
            ACCEPT_INVITE_URL,
            {"token": str(invite.invite_token)},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        invite.refresh_from_db()
        assert invite.user == existing_user


# ── Endpoint público de staff ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestPublicProviderStaff:
    """
    Feature: Endpoint público de equipe
    Como visitante
    Quero ver os profissionais disponíveis
    Para escolher quem vai me atender
    """

    def test_public_staff_returns_active_only(self, db: None) -> None:
        """
        Scenario: Somente staff ativo é exibido
          Given provider com staff ativo e inativo
          When GET /{slug}/staff/
          Then retorna apenas ativo
        """
        provider = ProviderProfileFactory(is_published=True)
        StaffFactory(provider=provider, name="Ativo", is_active=True)
        StaffFactory(provider=provider, name="Inativo", is_active=False)

        resp = APIClient().get(f"/api/v1/providers/{provider.slug}/staff/")
        assert resp.status_code == status.HTTP_200_OK
        names = [s["name"] for s in resp.json()]
        assert "Ativo" in names
        assert "Inativo" not in names

    def test_public_staff_filtered_by_service_id(self, db: None) -> None:
        """
        Scenario: Filtro por service_id
          Given service com apenas staff1 vinculado
          When GET /{slug}/staff/?service_id=
          Then retorna somente staff1
        """
        provider = ProviderProfileFactory(is_published=True)
        service = ServiceFactory(provider=provider, is_active=True, is_online=True)
        staff1 = StaffFactory(provider=provider, name="Vinculado", is_active=True)
        StaffFactory(provider=provider, name="Não Vinculado", is_active=True)
        ServiceStaff.objects.create(service=service, staff=staff1)

        resp = APIClient().get(f"/api/v1/providers/{provider.slug}/staff/?service_id={service.pk}")
        assert resp.status_code == status.HTTP_200_OK
        names = [s["name"] for s in resp.json()]
        assert "Vinculado" in names
        assert "Não Vinculado" not in names

    def test_public_staff_no_auth_required(self, db: None) -> None:
        """
        Scenario: Sem autenticação retorna 200
        """
        provider = ProviderProfileFactory(is_published=True)
        StaffFactory(provider=provider, is_active=True)
        resp = APIClient().get(f"/api/v1/providers/{provider.slug}/staff/")
        assert resp.status_code == status.HTTP_200_OK


# ── Signal: Staff owner criado com ProviderProfile ───────────────────────────


@pytest.mark.django_db
class TestOwnerStaffSignal:
    """
    Feature: Staff owner criado automaticamente
    Como sistema
    Quero garantir que todo provider tenha um staff owner
    Para que a lógica de permissões funcione desde o início
    """

    def test_creating_provider_profile_creates_owner_staff(self, db: None) -> None:
        """
        Scenario: Novo ProviderProfile gera Staff(role=owner)
          When um ProviderProfile é criado
          Then existe exatamente um Staff(role=owner) vinculado
        """
        profile = ProviderProfileFactory()
        assert Staff.objects.filter(provider=profile, role="owner").exists()
