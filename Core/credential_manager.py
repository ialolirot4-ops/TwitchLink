"""
Core/credential_manager.py

Utilidad para guardar tokens OAuth en el llavero seguro del sistema operativo
(Windows Credential Manager, macOS Keychain, o el proveedor de SecretService en Linux).

USO:
    from Core.credential_manager import CredentialManager

    ok  = CredentialManager.save_auth_token(username, token)
    tok = CredentialManager.get_auth_token(username)   # None si no existe
    ok  = CredentialManager.delete_auth_token(username)

NOTA: keyring puede no disponer de un backend en todas las configuraciones de Linux.
Si el backend no esta disponible, las operaciones fallan silenciosamente devolviendo
False/None para no interrumpir el flujo normal de la aplicacion.
"""

import keyring
import keyring.errors
from typing import Optional


class CredentialManager:
    SERVICE_NAME = "TwitchLinkApp"

    @staticmethod
    def save_auth_token(username: str, token: str) -> bool:
        """
        Guarda de forma segura el auth-token de Twitch asociado al usuario.
        Devuelve True si se guardo correctamente, False en caso de error.
        """
        try:
            keyring.set_password(CredentialManager.SERVICE_NAME, username, token)
            return True
        except Exception as e:
            print(f"[CredentialManager] Error al escribir credencial: {e}")
            return False

    @staticmethod
    def get_auth_token(username: str) -> Optional[str]:
        """
        Recupera el auth-token del llavero del sistema operativo.
        Devuelve None si no existe o si ocurre cualquier error.
        """
        try:
            return keyring.get_password(CredentialManager.SERVICE_NAME, username)
        except Exception as e:
            print(f"[CredentialManager] Error al leer credencial: {e}")
            return None

    @staticmethod
    def delete_auth_token(username: str) -> bool:
        """
        Elimina el auth-token del llavero del sistema operativo.
        Devuelve True si se elimino, False si no existia o hubo error.

        Captura tanto keyring.errors.PasswordDeleteError (credencial inexistente)
        como cualquier otra excepcion para cubrir backends no estandar en Linux.
        """
        try:
            keyring.delete_password(CredentialManager.SERVICE_NAME, username)
            return True
        except keyring.errors.PasswordDeleteError:
            # La credencial no existia previamente; no es un error real.
            return False
        except Exception as e:
            # Cubre backends alternativos que lanzan excepciones propias
            # (p. ej. SecretService no disponible, keyrings planos, etc.)
            print(f"[CredentialManager] Error al eliminar credencial: {e}")
            return False