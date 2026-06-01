import keyring
from typing import Optional

class CredentialManager:
    SERVICE_NAME = "TwitchLinkApp"

    @staticmethod
    def save_auth_token(username: str, token: str) -> bool:
        """
        Guarda de forma segura el auth-token de Twitch asociado a un nombre de usuario.
        """
        try:
            keyring.set_password(CredentialManager.SERVICE_NAME, username, token)
            return True
        except Exception as e:
            print(f"Error al escribir la credencial de forma segura: {e}")
            return False

    @staticmethod
    def get_auth_token(username: str) -> Optional[str]:
        """
        Recupera el auth-token del usuario guardado en el llavero del sistema operativo.
        """
        try:
            return keyring.get_password(CredentialManager.SERVICE_NAME, username)
        except Exception as e:
            print(f"Error al leer la credencial segura: {e}")
            return None

    @staticmethod
    def delete_auth_token(username: str) -> bool:
        """
        Elimina el auth-token almacenado del llavero del sistema operativo (p. ej., al cerrar sesión).
        """
        try:
            keyring.delete_password(CredentialManager.SERVICE_NAME, username)
            return True
        except keyring.errors.PasswordDeleteError:
            # La credencial no existía previamente
            return False
        except Exception as e:
            print(f"Error al intentar eliminar la credencial segura: {e}")
            return False