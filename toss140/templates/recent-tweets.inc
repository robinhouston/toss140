<div id="tweets" class="mini">
	<h2><a href="/recent{{q}}">Recently posted</a></h2>
	{% for tweet in recent_tweets %}
		{% include "tweetbox.inc" %}
	{% endfor %}
</div>
