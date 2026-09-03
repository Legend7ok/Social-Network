/**
 * The buttons on a picture and on a person: like, follow, share.
 *
 * The first two live on several pages each — the image page, the feed cards,
 * the people cards, the profile header — and every one of them used to carry
 * its own copy of the same request. One copy here instead, so a change to how
 * these calls are made is a change in one place.
 *
 * A signed-out visitor never reaches the server: the press opens the sign-in
 * dialog instead. The server would only answer 403, which the page had no way
 * of showing — the button looked broken.
 */
document.addEventListener('alpine:init', () => {
  function announce(text, tone = 'error') {
    Alpine.store('messages').push({ text, tone });
  }

  /**
   * Sends one action and reports whether the server took it. Anything other
   * than a plain acceptance is treated as "nothing happened", so the button
   * keeps showing what the server actually holds.
   */
  async function send(url, action) {
    let res;
    try {
      res = await fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': Alpine.store('csrf'),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action }),
      });
    } catch {
      // A connection that never arrived throws here rather than answering.
      announce('No connection. Please try again.');
      return false;
    }

    if (res.status === 429) {
      announce('Too many requests. Please slow down.');
      return false;
    }

    // The session ran out while the page stayed open. Saying so beats a button
    // that quietly stops working.
    if (res.status === 401 || res.status === 403) {
      announce('Your session has expired. Reload the page and try again.');
      return false;
    }

    const data = await res.json().catch(() => null);
    return data?.status === 'ok';
  }

  /**
   * The clipboard is refused outside a secure page, and the promise it returns
   * is rejected rather than throwing where you would look for it. Saying so is
   * the point: this used to claim success without copying anything.
   */
  async function copyLink(url) {
    try {
      await navigator.clipboard.writeText(url);
      announce('Link copied!', 'success');
    } catch {
      announce('Could not copy the link. Copy it from the address bar instead.');
    }
  }

  Alpine.data('likeButton', (url, liked, count) => ({
    liked,
    count,
    // A press while the last one is still in the air would send a second
    // opposite action and land on whichever answer came back last.
    busy: false,

    async toggle() {
      if (this.busy) return;
      if (!this.$store.signedIn) {
        this.$dispatch('auth-required', {
          message: 'Sign in to like this picture and keep it in your account.',
        });
        return;
      }

      this.busy = true;
      try {
        if (!(await send(url, this.liked ? 'unlike' : 'like'))) return;
        this.liked = !this.liked;
        this.count += this.liked ? 1 : -1;
      } finally {
        this.busy = false;
      }
    },
  }));

  Alpine.data('followButton', (url, following) => ({
    following,
    busy: false,

    async toggle() {
      if (this.busy) return;
      if (!this.$store.signedIn) {
        this.$dispatch('auth-required', {
          message: 'Sign in to follow people and see their new pictures.',
        });
        return;
      }

      this.busy = true;
      try {
        if (!(await send(url, this.following ? 'unfollow' : 'follow'))) return;
        this.following = !this.following;
      } finally {
        this.busy = false;
      }
    },
  }));

  Alpine.data('shareButton', (title) => ({
    /**
     * The system's own share menu where there is one — every phone, and Chrome,
     * Edge and Safari on the desktop — and the clipboard everywhere else.
     * Sharing is offered from a picture's own page, so the address bar already
     * holds the link worth passing on.
     */
    async share() {
      const url = window.location.href;

      if (navigator.share) {
        try {
          await navigator.share({ title, url });
          return;
        } catch (error) {
          // Closing the menu is an answer, not a failure.
          if (error.name === 'AbortError') return;
        }
      }

      await copyLink(url);
    },
  }));
});
