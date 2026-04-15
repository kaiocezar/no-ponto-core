"""Testes do model User — exemplo de teste unitário."""

import pytest

from apps.accounts.models import User


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_with_email(self) -> None:
        user = User.objects.create_user(email="teste@email.com", password="senha123")
        assert user.email == "teste@email.com"
        assert user.check_password("senha123")
        assert user.role == User.Role.CLIENT

    def test_create_user_with_phone(self) -> None:
        user = User.objects.create_user(phone_number="+5511999999999")
        assert user.phone_number == "+5511999999999"
        assert not user.has_usable_password()

    def test_create_user_without_email_or_phone_raises(self) -> None:
        with pytest.raises(ValueError, match="email ou telefone"):
            User.objects.create_user()

    def test_user_str_returns_full_name(self) -> None:
        user = User(full_name="João Silva")
        assert str(user) == "João Silva"

    def test_user_anonymize(self) -> None:
        user = User.objects.create_user(
            email="joao@email.com",
            phone_number="+5511999999999",
            full_name="João Silva",
        )
        user.anonymize()
        assert user.email is None
        assert user.phone_number is None
        assert "deletado" in user.full_name
        assert user.is_deleted is True
        assert user.is_active is False
