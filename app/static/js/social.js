/**
 * The like and follow buttons.
 *
 * Both live on several pages each — the image page, the feed cards, the people
 * cards, the profile header — and every one of them used to carry its own copy
 * of the same request. One copy here instead, so a change to how these calls
 * are made is a change in one place.
 *
 * A signed-out visitor never reaches the server: the press opens the sign-in
 * dialog instead. The server would only answer 403, which the page had no way
 * of showing — the button looked broken.
 */
document.addEventListener('alpine:init', () => {
  /**
   * Sends one action and reports whether the server took it. Anything other
   * than a plain acceptance is treated as "nothing happened", so the button
   * keeps showing what the server actually holds.
   */
  async function send(url, action) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': Alpine.store('csrf'),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ action }),
    });

    if (res.status === 429) {
      Alpine.store('messages').push('Too many requests. Please slow down.');
      return false;
    }

    const data = await res.json().catch(() => null);
    return data?.status === 'ok';
  }

  Alpine.data('likeButton', (url, liked, count) => ({
    liked,
    count,

    async toggle() {
      if (!this.$store.signedIn) {
        this.$dispatch('auth-required', {
          message: 'Sign in to like this picture and keep it in your account.',
        });
        return;
      }
      if (!(await send(url, this.liked ? 'unlike' : 'like'))) return;
      this.liked = !this.liked;
      this.count += this.liked ? 1 : -1;
    },
  }));

  Alpine.data('followButton', (url, following) => ({
    following,

    async toggle() {
      if (!this.$store.signedIn) {
        this.$dispatch('auth-required', {
          message: 'Sign in to follow people and see their new pictures.',
        });
        return;
      }
      if (!(await send(url, this.following ? 'unfollow' : 'follow'))) return;
      this.following = !this.following;
    },
  }));
});
