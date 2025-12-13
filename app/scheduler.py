import json
import os
import time
import threading
import datetime
from typing import Dict, List, Optional, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
LOCK_DIR = Path(__file__).resolve().parent.parent / 'locks'
LOCK_DIR.mkdir(exist_ok=True)

class PostScheduler:
    def __init__(self, data_file: str = "scheduled_posts.json"):
        self.data_file = data_file
        self.data = self._load_data()
        self.running = False
        self.thread = None
        self.check_interval = 30  # sprawdzaj co 30 sekund
        
    def _load_data(self) -> Dict:
        """Ładuje dane z pliku JSON z mechanizmem recovery"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Sprawdź czy struktura jest poprawna
                    if not all(key in data for key in ['scheduled', 'published', 'failed', 'metadata']):
                        logger.warning("Niepoprawna struktura danych, tworzę nową")
                        return self._create_empty_data()
                    return data
            else:
                return self._create_empty_data()
        except Exception as e:
            logger.error(f"Błąd ładowania danych: {e}")
            # Backup uszkodzonego pliku
            if os.path.exists(self.data_file):
                backup_name = f"{self.data_file}.backup_{int(time.time())}"
                os.rename(self.data_file, backup_name)
                logger.info(f"Uszkodzony plik przeniesiony do: {backup_name}")
            return self._create_empty_data()
    
    def _create_empty_data(self) -> Dict:
        """Tworzy pustą strukturę danych"""
        return {
            "scheduled": [],
            "published": [],
            "failed": [],
            "metadata": {
                "version": "1.0",
                "last_check": None,
                "next_check": None
            }
        }
    
    def _save_data(self):
        """Zapisuje dane do pliku JSON z odpornym na Windows retry."""
        temp_file = f"{self.data_file}.tmp"
        last_err = None
        for attempt in range(5):
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
                # Użyj os.replace zawsze – na Windows może nadal rzucić błąd przy otwartym uchwycie
                os.replace(temp_file, self.data_file)
                return
            except Exception as e:
                last_err = e
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception:
                    pass
                time.sleep(0.2 * (attempt + 1))
        # Po niepowodzeniu wszystkich prób zloguj błąd
        logger.error(f"Błąd zapisywania danych po wielu próbach: {last_err}")
    
    def schedule_post(self, clip_id: str, scheduled_at: str, caption: str = "", 
                     accounts: List[str] = None, retry_count: int = 0) -> str:
        """Planuje publikację posta"""
        post_id = f"post_{int(time.time())}_{clip_id}"
        
        post_data = {
            "id": post_id,
            "clip_id": clip_id,
            "scheduled_at": scheduled_at,
            "caption": caption,
            "accounts": accounts or [],
            "status": "pending",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "retry_count": retry_count,
            "max_retries": 3,
            "last_attempt": None,
            "error_message": None
        }
        
        self.data["scheduled"].append(post_data)
        self._save_data()
        
        logger.info(f"Zaplanowano post {post_id} na {scheduled_at}")
        return post_id
    
    def get_scheduled_posts(self) -> List[Dict]:
        """Zwraca listę zaplanowanych postów"""
        return self.data["scheduled"]
    
    def get_published_posts(self) -> List[Dict]:
        """Zwraca listę opublikowanych postów"""
        return self.data["published"]
    
    def get_failed_posts(self) -> List[Dict]:
        """Zwraca listę postów z błędami"""
        return self.data["failed"]

    def add_published_post(self, clip_id: str, caption: str = "", accounts: List[str] | None = None, scheduled_at: Optional[str] = None) -> str:
        """Dodaje wpis do listy opublikowanych (dla publikacji natychmiastowych)."""
        post_id = f"post_{int(time.time())}_{clip_id}"
        post_data = {
            "id": post_id,
            "clip_id": clip_id,
            "scheduled_at": scheduled_at,
            "caption": caption,
            "accounts": accounts or [],
            "status": "published",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "published_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.data["published"].append(post_data)
        self._save_data()
        logger.info(f"Dodano opublikowany post {post_id} (clip_id={clip_id}) do timeline")
        return post_id
    
    def remove_scheduled_post(self, post_id: str) -> bool:
        """Usuwa zaplanowany post"""
        for i, post in enumerate(self.data["scheduled"]):
            if post["id"] == post_id:
                del self.data["scheduled"][i]
                self._save_data()
                logger.info(f"Usunięto zaplanowany post {post_id}")
                return True
        return False
    
    def _move_post_to_published(self, post: Dict):
        """Przenosi post do listy opublikowanych"""
        post["status"] = "published"
        post["published_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Usuń z scheduled
        self.data["scheduled"] = [p for p in self.data["scheduled"] if p["id"] != post["id"]]
        # Dodaj do published
        self.data["published"].append(post)
        self._save_data()
    
    def _move_post_to_failed(self, post: Dict, error_message: str):
        """Przenosi post do listy nieudanych"""
        post["status"] = "failed"
        post["failed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        post["error_message"] = error_message
        
        # Usuń z scheduled
        self.data["scheduled"] = [p for p in self.data["scheduled"] if p["id"] != post["id"]]
        # Dodaj do failed
        self.data["failed"].append(post)
        self._save_data()
    
    def _retry_post(self, post: Dict, error_message: str):
        """Ponawianie wyłączone: przenosi post bezpośrednio do failed."""
        post["last_attempt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        post["error_message"] = error_message
        # Zamiast planować kolejną próbę, natychmiast oznacz jako failed
        self._move_post_to_failed(post, f"Wyłączono auto-ponawianie: {error_message}")
    
    def _acquire_post_lock(self, post_id: str) -> bool:
        """Probuje utworzyć ekskluzywną blokadę dla posta. Zwraca True, jeśli zdobędzie."""
        try:
            lock_path = LOCK_DIR / f'post_{post_id}.lock'
            # O_EXCL zapewnia atomowe utworzenie; jeśli plik istnieje, rzuci wyjątek
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f'{os.getpid()}'.encode('utf-8'))
            finally:
                os.close(fd)
            return True
        except FileExistsError:
            return False
        except Exception:
            # Nie udało się utworzyć blokady – na wszelki wypadek traktuj jako brak
            return False
    
    def _release_post_lock(self, post_id: str) -> None:
        try:
            lock_path = LOCK_DIR / f'post_{post_id}.lock'
            if lock_path.exists():
                lock_path.unlink(missing_ok=True)
        except Exception:
            pass
    
    def _check_and_publish_posts(self):
        """Sprawdza i publikuje posty, które są gotowe"""
        now = datetime.datetime.now(datetime.timezone.utc)
        posts_to_publish = []
        
        for post in self.data["scheduled"]:
            try:
                scheduled_at_str = post["scheduled_at"]
                # Dodaj timezone jeśli go nie ma
                if '+' not in scheduled_at_str and 'Z' not in scheduled_at_str:
                    scheduled_at_str += '+00:00'
                scheduled_time = datetime.datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
                if scheduled_time <= now:
                    posts_to_publish.append(post)
            except Exception as e:
                logger.error(f"Błąd parsowania daty dla posta {post['id']}: {e}")
                self._move_post_to_failed(post, f"Błąd parsowania daty: {e}")
        
        for post in posts_to_publish:
            # Guard: jeśli post nie jest w stanie 'pending', pomiń
            if str(post.get('status','')).lower() not in ('pending','scheduled'):
                continue
            # Spróbuj zdobyć blokadę – jeśli ktoś inny publikuje, pomiń
            if not self._acquire_post_lock(post['id']):
                continue
            try:
                # Zmien stan na 'publishing' i zapisz – inni pominą
                post['status'] = 'publishing'
                post['last_attempt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                # Zapisz aktualny obiekt w scheduled
                for i, p in enumerate(self.data['scheduled']):
                    if p['id'] == post['id']:
                        self.data['scheduled'][i] = post
                        break
                self._save_data()

                success = self._publish_post(post)
                if success:
                    self._move_post_to_published(post)
                    logger.info(f"Opublikowano post {post['id']}")
                else:
                    self._retry_post(post, "Publikacja nie powiodła się")
            except Exception as e:
                logger.error(f"Błąd publikacji posta {post['id']}: {e}")
                self._retry_post(post, str(e))
            finally:
                self._release_post_lock(post['id'])

    def _publish_post(self, post: Dict) -> bool:
        """Publikuje post - rzeczywista implementacja"""
        try:
            logger.info(f"Publikuję post {post['id']} dla klipu {post['clip_id']}")
            
            # Importuj funkcje z main.py
            import requests
            import json
            
            # Przygotuj dane do publikacji
            publish_data = {
                'caption': post.get('caption', ''),
                'publer_account_ids': post.get('accounts', []),
                'publish_now': True,  # publikuj natychmiast
                'use_internal_scheduler': False  # nie używaj schedulera (już jesteśmy w nim)
            }
            
            # Wywołaj lokalny endpoint publikacji
            try:
                response = requests.post(
                    f'http://127.0.0.1:5001/publish/{post["clip_id"]}',
                    json=publish_data,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('ok', False):
                        logger.info(f"Post {post['id']} opublikowany pomyślnie")
                        return True
                    else:
                        logger.error(f"Publikacja posta {post['id']} nie powiodła się: {result.get('error', 'Unknown error')}")
                        return False
                else:
                    logger.error(f"HTTP error {response.status_code} podczas publikacji posta {post['id']}")
                    return False
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error podczas publikacji posta {post['id']}: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Błąd publikacji posta {post['id']}: {e}")
            return False
    
    def _scheduler_loop(self):
        """Główna pętla schedulera"""
        while self.running:
            try:
                self.data["metadata"]["last_check"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._check_and_publish_posts()
                
                # Następne sprawdzenie
                next_check = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=self.check_interval)
                self.data["metadata"]["next_check"] = next_check.isoformat()
                self._save_data()
                
            except Exception as e:
                logger.error(f"Błąd w pętli schedulera: {e}")
            
            time.sleep(self.check_interval)
    
    def start(self):
        """Uruchamia scheduler"""
        if self.running:
            logger.warning("Scheduler już działa")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
        logger.info("Scheduler uruchomiony")
    
    def stop(self):
        """Zatrzymuje scheduler"""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Scheduler zatrzymany")
    
    def get_status(self) -> Dict:
        """Zwraca status schedulera"""
        return {
            "running": self.running,
            "scheduled_count": len(self.data["scheduled"]),
            "published_count": len(self.data["published"]),
            "failed_count": len(self.data["failed"]),
            "last_check": self.data["metadata"]["last_check"],
            "next_check": self.data["metadata"]["next_check"]
        }
    
    def push_all_to_publer(self) -> Dict:
        """Pushuje wszystkie zaplanowane posty do Publera jako backup"""
        pushed_count = 0
        failed_count = 0
        
        for post in self.data["scheduled"][:]:  # kopia listy
            try:
                logger.info(f"Pushowanie posta {post['id']} do Publera")
                
                # Przygotuj dane dla Publera
                publer_data = {
                    'clip_id': post['clip_id'],
                    'caption': post['caption'],
                    'scheduled_at': post['scheduled_at'],
                    'publish_now': False,  # zawsze planuj w Publerze
                    'publer_account_ids': post.get('accounts', [])
                }
                
                # TODO: Wywołaj API Publera
                # Na razie symulacja sukcesu
                success = True
                
                if success:
                    pushed_count += 1
                    # Usuń z lokalnej kolejki po udanym pushu
                    self.remove_scheduled_post(post["id"])
                    logger.info(f"Post {post['id']} przeniesiony do Publera")
                else:
                    failed_count += 1
                    logger.error(f"Nie udało się przenieść posta {post['id']} do Publera")
                
            except Exception as e:
                logger.error(f"Błąd pushowania posta {post['id']} do Publera: {e}")
                failed_count += 1
        
        return {
            "pushed": pushed_count,
            "failed": failed_count,
            "total": pushed_count + failed_count
        }

    def push_post_to_publer(self, post_id: str, publish_now: bool = False) -> bool:
        """Pushuje konkretny post do Publera jako backup
        publish_now=True -> wysyła natychmiast do kolejki Publera
        publish_now=False -> planuje wg post.scheduled_at
        """
        try:
            # Znajdź post
            post = None
            for p in self.data["scheduled"]:
                if p["id"] == post_id:
                    post = p
                    break
            
            if not post:
                logger.error(f"Nie znaleziono posta {post_id}")
                return False
            
            logger.info(f"Pushowanie posta {post_id} do Publera (publish_now={publish_now})")
            
            # Przygotuj dane dla Publera
            publer_data = {
                'caption': post['caption'],
                'scheduled_at': post['scheduled_at'] if not publish_now else None,
                'publish_now': True if publish_now else False,
                'publer_account_ids': post.get('accounts', []),
                'use_internal_scheduler': False  # używaj Publera, nie wewnętrznego schedulera
            }
            
            # Wywołaj API Publera przez lokalny endpoint
            import requests
            try:
                response = requests.post(
                    f'http://127.0.0.1:5001/publish/{post["clip_id"]}',
                    json=publer_data,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    success = result.get('ok', False)
                    if not success:
                        logger.error(f"Błąd pushowania posta {post_id} do Publera: {result}")
                    else:
                        logger.info(f"Post {post_id} przeniesiony do Publera (publish_now={publish_now})")
                    return bool(success)
                else:
                    logger.error(f"HTTP {response.status_code} podczas pushowania posta {post_id} do Publera: {response.text}")
                    return False
            except Exception as e:
                logger.error(f"Wyjątek podczas pushowania posta {post_id} do Publera: {e}")
                return False
        except Exception as e:
            logger.error(f"Nieoczekiwany błąd pushowania posta {post_id} do Publera: {e}")
            return False

    def update_scheduled_post(self, post_id: str, update_data: Dict) -> bool:
        """Aktualizuje zaplanowany post"""
        try:
            # Znajdź post
            post = None
            for p in self.data["scheduled"]:
                if p["id"] == post_id:
                    post = p
                    break
            
            if not post:
                logger.error(f"Nie znaleziono posta {post_id}")
                return False
            
            # Aktualizuj dozwolone pola
            allowed_fields = ['scheduled_at', 'caption', 'accounts']
            for field, value in update_data.items():
                if field in allowed_fields:
                    post[field] = value
                    logger.info(f"Zaktualizowano pole {field} dla posta {post_id}")
            
            # Zapisz zmiany
            self._save_data()
            logger.info(f"Post {post_id} zaktualizowany pomyślnie")
            return True
            
        except Exception as e:
            logger.error(f"Błąd aktualizacji posta {post_id}: {e}")
            return False

    def reset_failed_posts(self) -> int:
        """Przenosi wszystkie posty z failed z powrotem do scheduled"""
        try:
            reset_count = 0
            posts_to_reset = self.data["failed"].copy()
            
            for post in posts_to_reset:
                # Resetuj status i błędy
                post["status"] = "pending"
                post["error_message"] = None
                post["failed_at"] = None
                post["retry_count"] = 0
                
                # Przenieś z failed do scheduled
                self.data["scheduled"].append(post)
                reset_count += 1
            
            # Wyczyść listę failed
            self.data["failed"] = []
            
            # Zapisz zmiany
            self._save_data()
            logger.info(f"Zresetowano {reset_count} postów z failed do scheduled")
            return reset_count
            
        except Exception as e:
            logger.error(f"Błąd resetowania postów: {e}")
            return 0

    def clean_published_older_than(self, hours: int = 48) -> int:
        """Usuwa opublikowane posty starsze niż `hours` godzin od published_at."""
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            cutoff = now - datetime.timedelta(hours=hours)
            kept = []
            removed = 0
            for post in self.data.get("published", []):
                ts_str = post.get("published_at") or post.get("scheduled_at") or post.get("created_at")
                dt = None
                if ts_str:
                    try:
                        if '+' not in ts_str and 'Z' not in ts_str:
                            ts_str += '+00:00'
                        dt = datetime.datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    except Exception as e:
                        logger.error(f"Błąd parsowania daty dla posta {post.get('id') or post.get('clip_id')}: {e}")
                if dt and dt <= cutoff:
                    removed += 1
                else:
                    kept.append(post)
            self.data["published"] = kept
            if removed:
                self._save_data()
            logger.info(f"Wyczyszczono {removed} postów z published starszych niż {hours}h")
            return removed
        except Exception as e:
            logger.error(f"Błąd czyszczenia opublikowanych postów: {e}")
            return 0

# Globalna instancja schedulera
scheduler = PostScheduler()

def retry_failed_post(self, post_id: str) -> bool:
    """Ręcznie ponawia publikację nieudanego posta.
    Zwraca True przy sukcesie, False gdy publikacja znów się nie uda.
    """
    try:
        for i, post in enumerate(self.data.get("failed", [])):
            if post.get("id") == post_id:
                # lock guard
                if not self._acquire_post_lock(post_id):
                    return False
                try:
                    post["last_attempt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    post['status'] = 'publishing'
                    success = self._publish_post(post)
                    if success:
                        post["status"] = "published"
                        post["published_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                        self.data["failed"].pop(i)
                        self.data.setdefault("published", []).append(post)
                        self._save_data()
                        return True
                    else:
                        post["error_message"] = "Publikacja nie powiodła się"
                        post['status'] = 'failed'
                        self.data["failed"][i] = post
                        self._save_data()
                        return False
                except Exception as e:
                    post["error_message"] = str(e)
                    self.data["failed"][i] = post
                    self._save_data()
                    return False
        return False
    except Exception:
        return False