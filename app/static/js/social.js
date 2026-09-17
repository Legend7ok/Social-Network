/**
 * The buttons on a picture and on a person: like, follow, share - and the
 * form a comment is written in.
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
   * The words for a request the server turned away, shared by every button
   * and form so the same refusal never reads two different ways.
   */
  function explainRefusal(status) {
    if (status === 429) return 'Too many requests. Please slow down.';
    // The session ran out while the page stayed open. Saying so beats a
    // control that quietly stops working.
    if (status === 401 || status === 403) {
      return 'Your session has expired. Reload the page and try again.';
    }
    return null;
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

    const refusal = explainRefusal(res.status);
    if (refusal) {
      announce(refusal);
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

  /**
   * htmx swaps in only the answers that went through, so a refused request
   * would otherwise leave the page sitting there as if nothing happened.
   */
  const htmxRefusals = {
    refused(status) {
      announce(explainRefusal(status) ?? 'Something went wrong. Please try again.');
    },

    offline() {
      announce('No connection. Please try again.');
    },
  };

  Alpine.data('commentForm', () => ({ ...htmxRefusals }));

  /**
   * One dialog for every comment on the page, told what to take down by the
   * `confirm-comment-removal` event its Delete button sends. The request goes
   * out from the dialog's own button, so the refusals above bubble up to it.
   */
  Alpine.data('commentRemoval', () => ({
    ...htmxRefusals,
    confirming: false,
    busy: false,
    url: '',
    target: '',

    ask({ url, target }) {
      this.url = url;
      this.target = target;
      this.confirming = true;
    },

    async confirm() {
      if (this.busy) return;
      this.busy = true;
      try {
        await htmx.ajax('POST', this.url, {
          source: this.$refs.confirm,
          target: this.target,
          swap: 'outerHTML',
          headers: { 'X-CSRFToken': Alpine.store('csrf') },
        });
      } catch {
        // A request that never arrived was already announced by offline().
      } finally {
        this.busy = false;
        this.confirming = false;
      }
    },
  }));

  /**
   * The answer box of one comment, shared by every Reply button in its
   * thread. The box names the person being answered: a thread is one level
   * deep, so an answer to an answer lands under the same comment, and the
   * name is what tells everyone who it was meant for.
   */
  Alpine.data('replyBox', () => ({
    replying: false,
    draft: '',

    open(username) {
      this.replying = true;
      this.draft = `@${username} `;
      this.$nextTick(() => {
        const box = this.$root.querySelector('textarea[name="body"]');
        box.focus();
        box.setSelectionRange(box.value.length, box.value.length);
      });
    },

    close() {
      this.replying = false;
      this.draft = '';
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
