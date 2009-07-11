{% if not tweet.is_retweet %}
	<div class="tweet">
		&quot;{{tweet.text|escape}}&quot;
		{%if admin%}
			<a class="admin" href="/admin/datastore/edit?key={{tweet.key}}&amp;kind=Tweet&amp;next={{this_page|urlencode}}">e</a>
			<a class="admin" href="/do/index-tweet?key={{tweet.key}}">r</a>
		{%endif%}
		<div class="tweeter"><a
			 href="http://twitter.com/{{tweet.from_user}}/status/{{tweet.id}}">{{tweet.from_user}}</a>
		</div>
	</div>
{% endif %}
