"""Factories para testes de accounts."""

import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import User


class UserFactory(DjangoModelFactory):
    """Factory para criação de usuários nos testes."""

    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@exemplo.com")
    full_name = factory.Faker("name", locale="pt_BR")
    role = User.Role.CLIENT
    auth_provider = User.AuthProvider.EMAIL
    is_active = True

    @factory.post_generation
    def password(self, create: bool, extracted: str | None, **kwargs: object) -> None:
        raw = extracted or "senha_segura_123"
        self.set_password(raw)
        if create:
            self.save(update_fields=["password"])


class ProviderUserFactory(UserFactory):
    """Factory para criação de prestadores nos testes."""

    role = User.Role.PROVIDER
    email = factory.Sequence(lambda n: f"prestador{n}@exemplo.com")
