{# included in lists of tweets - as distinct from lists of articles #}
{% if tweet.long_url and not tweet.is_retweet %}
	<div class="tweetbox">
		<div class="tweet">&ldquo;<a
				onclick="pageTracker._trackPageview('/outbound/from_text/{{ tweet.key.name }}');"
				href="{{ tweet.long_url|escape }}">{{ tweet.text|escape }}</a>&rdquo;
			{%if admin%}
				<span class="admin"><a class="admin" href="/admin/datastore/edit?key={{ tweet.key }}&amp;kind=Tweet&amp;next={{ refresh_url|urlencode }}">e</a></span>
			{%endif%}
		</div>
		<div class="meta">
			–&nbsp;
			{% if front %}
				<a href="/tweeter/{{ tweet.from_user }}{{q}}">{{ tweet.from_user }}</a>
				{% if tweet.article %}
					on
					{% if tweet.article.author %}
						<a href="/author/{{ tweet.article.author|urlencode }}{{q}}">{{ tweet.article.author }}</a>
					{% else %}
						something from <a href="/organ/{{ tweet.article.parent.name|urlencode }}{{q}}">{{ tweet.article.parent.name }}</a>
					{% endif %}
					<a class="tau"
						onclick="javascript:pageTracker._trackPageview('/outbound/status/{{ tweet.id }}');"
						href="http://twitter.com/{{tweet.from_user}}/status/{{tweet.id}}">#</a>
				{% endif %}
			{% else %}
				{%if tweet.article.author %}
					<a href="/author/{{ tweet.article.author|urlencode }}{{q}}">{{ tweet.article.author }}</a>, {%else%}from {%endif%}
					<a href="/organ/{{ tweet.article.parent.name|urlencode }}{{q}}">{{ tweet.article.parent.name }}</a><!--
						-->{%if tweet.article.date%}, <a href="/date/{{ tweet.article.date }}{{q}}">{{ tweet.article.date|date:"D jS F Y" }}</a>{%endif%}
			
					<div class="tweeter"><a href="http://twitter.com/{{ tweet.from_user }}/status/{{ tweet.id }}{{q}}">{{ tweet.from_user }}</a></div>
				{% endif %}
			
				{%if admin%}
					<span class="admin">
						<a class="admin" href="/admin/datastore/edit?key={{ tweet.article.key }}&amp;kind=Article&amp;next={{ refresh_url|urlencode }}">e</a>
						<a class="admin" href="/do/index-tweet?key={{ tweet.key }}">r</a>
					</span>
				{%endif%}
		</div>
	</div>
{% endif %}
