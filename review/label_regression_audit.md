# Label regression audit

Rows: 69. FIXED 67, PARTIAL 2, SAME 0, REGRESSED 0.

Every id was compiled live with `tools/compile_card.py --card`; artifact evidence is from `compile_standard.jsonl` SHA `e35ef8b4...`.

| id | pack | verdict | status | evidence |
|---|---|---|---|---|
| Z003 | v6 | legit | FIXED | card.anaphor=true; card_type={kind:this_card,value:~} |
| Z004 | v6 | bug | FIXED | type=static_ability; keyword=Warp; cost=pay_mana {1}{R} |
| Z015 | v6 | bug | FIXED | who={kind:owner_of,of:{kind:anaphora,ref:the_exiled_card}} |
| Z018 | v6 | bug | FIXED | card_type={kind:anaphora,ref:the_exiled_card,status:unresolved} |
| Z030 | v6 | bug | FIXED | modifier={kind:attached_to,target:{kind:anaphora,ref:that_creature}} |
| Z035 | v6 | legit | FIXED | one count only: effect.count=1; counter={kind:coin} |
| Z040 | v6 | legit | FIXED | trigger.event.kind=event_ref; anaphor=true |
| Z044 | v6 | legit | FIXED | effect={verb:must_block,if_able:true,inner:{verb:block,card:...}}; duplicate top-level if_able removed |
| Z047 | v6 | bug | FIXED | add_mana symbol {C}; no on/source object for mana |
| Z048 | v6 | legit | FIXED | card.zone={prep:from,zone:graveyard,possessor:your}; to={zone:hand,owner:you,prep:to}; both canonical prep/zone/owner-or-possessor shape |
| Z049 | v6 | bug | FIXED | trigger.event.object.card_type=[instant,sorcery]; card_class=spell |
| Z051 | v6 | bug | FIXED | to.owner={kind:owner_of,of:{kind:anaphora,ref:its}} |
| Z052 | v6 | bug | FIXED | IR L0->0:intra:that_many; amount.of.that_many.link=L0->0:intra:that_many |
| Z053 | v6 | bug | FIXED | to.card_type=[creature,planeswalker]; quantifier=target |
| Z059 | v6 | bug | FIXED | effect={verb:shared_effects,shared:{who:any number...},items:[mill,lose_life]} |
| Z061 | v6 | legit | FIXED | look effect has source=top |
| Z062 | v6 | bug | FIXED | cost.card.modifier={kind:attached_to,target:{kind:this_card,value:~}} |
| Z064 | v6 | legit | PARTIAL | effect={verb:may,inner:{verb:pay}}; whole may/pay ability not split |
| Z067 | v6 | bug | FIXED | card.any_of=true; card_type=[Goblin,Swamp,Mountain] |
| Z068 | v6 | bug | FIXED | type=static_ability; keyword=Sneak; cost=pay_mana {3}{B}{B} |
| Z072 | v6 | legit | FIXED | token.colors=[blue,black] |
| Z074 | v6 | bug | FIXED | type=static_ability; keyword=Warp; cost=pay_mana {1}{U} |
| Z076 | v6 | bug | FIXED | type=static_ability; keyword=Warp; cost=pay_mana {1}{G} |
| Z079 | v6 | legit | FIXED | on.card_type={kind:this_card,value:~}; anaphor=true |
| Z082 | v6 | legit | FIXED | on.card_type={kind:this_card,value:~}; anaphor=true |
| Z084 | v6 | legit | FIXED | on.card_type={kind:this_card,value:~}; anaphor=true |
| Z085 | v6 | legit | FIXED | card.card_type={kind:this_card,value:~}; anaphor=true |
| Z086 | v6 | bug | FIXED | effect=shared_effects, shared.target={creature,target} |
| Z092 | v6 | bug | FIXED | for_each.items={kind:type,value:creature,controller:you,modifier:{stat_filter,power>=4}} |
| Z093 | v6 | bug | FIXED | effect={verb:may,inner:{verb:discard}} |
| Z095 | v6 | bug | FIXED | amount.set.card_type=[{kind:zone_set,zone:{zone:hand,possessor:target opponent}}] |
| Z099 | v6 | legit | FIXED | card.anaphor=true; card_type={kind:this_card,value:~} |
| A002 | v7 | bug | FIXED | effect.kind=mana_loss_disabled; when=steps and phases end |
| A004 | v7 | bug | FIXED | IR L2->1:anaphora:that_card; put.card.card_type={kind:link,link:L2->1:anaphora:that_card} |
| A009 | v7 | legit | FIXED | target.exclude_self=true |
| A010 | v7 | legit | FIXED | effect={verb:choose,object:one} kept as one ability; no split |
| A012 | v7 | bug | FIXED | effect.kind=gift_ability; gift_self=true |
| A021 | v7 | legit | PARTIAL | output untap each creature; fixture lacks the "those creatures" oracle text, so intent cannot be fully verified |
| A022 | v7 | legit | FIXED | condition.event_ref; IR event_positive link 2->1 |
| A026 | v7 | bug | FIXED | attach object/to ref=manifested_creature,status=resolved |
| A028 | v7 | bug | FIXED | label.quantifier=target; card_type=[attacking creature, blocking creature] |
| A031 | v7 | bug | FIXED | quote.quoted_text preserved; token=Beau; named=[Beau]; target this_card/~ |
| A033 | v7 | bug | FIXED | artifact amount.of={kind:that_many,link:L0->0:intra:that_many}; quantifier={relation:>=,amount:1}; IR intra kept |
| A035 | v7 | bug | FIXED | blocked_by.max=1 |
| A046 | v7 | legit | FIXED | effect.count=1; counter={kind:+1/+1} |
| A047 | v7 | legit | FIXED | destination.library_position=second_from_top_or_bottom |
| A050 | v7 | legit | FIXED | effect.count=1; counter={kind:stun} |
| A051 | v7 | legit | FIXED | quote.quoted_text preserved; sentence type activated |
| A055 | v7 | legit | FIXED | card.controller=target player; to.zone=hand; owner=owner_of |
| A056 | v7 | bug | FIXED | amount={kind:computed,stat:total_mana_value,exclude_self:true} |
| A058 | v7 | legit | FIXED | effect.count=X; counter={kind:+1/+1}; xdef count |
| A064 | v7 | bug | FIXED | effect.amount={kind:x}; xdef count |
| A065 | v7 | bug | FIXED | duration={kind:until,event:exile,card:a nonland card} |
| A070 | v7 | legit | FIXED | artifact amount.of={kind:that_many,link:L0->0:intra:that_many}; IR intra kept |
| A079 | v7 | legit | FIXED | quote.quoted_text preserved; sentence type activated |
| A084 | v7 | bug | FIXED | trigger.event.any_of=[play land,cast spell] |
| A089 | v7 | legit | FIXED | effect.count=4; counter={kind:-1/-1} |
| A092 | v7 | bug | FIXED | attach object/to ref=manifested_creature,status=resolved |
| A095 | v7 | legit | FIXED | artifact amount={kind:count_of,of:{link:L1->0:quantity:this_way}}; no prose |
| B007 | v8 | legit | FIXED | effect.or={kind:or,items:[sacrifice,pay_mana]}; or_pay retained |
| B011 | v8 | legit | FIXED | counters field removed; counter={kind:all,possessor:{kind:anaphora,ref:its}} |
| B018 | v8 | bug | FIXED | modifier.total=true on stat mana value |
| B019 | v8 | bug | FIXED | cost target card_type.value=card; target.zone={prep:from,zone:graveyard,possessor:your} |
| B020 | v8 | legit | FIXED | effect.xdef={kind:x,source:mana_cost} |
| B023 | v8 | bug | FIXED | to.status=[attacking,blocking]; status_logic=or |
| B029 | v8 | legit | FIXED | effect.xdef={kind:x,source:mana_cost} |
| B034 | v8 | bug | FIXED | artifact amount.of={kind:that_many,link:L2->2:intra:that_many}; IR intra kept |
| B036 | v8 | bug | FIXED | artifact type=keyword_action; keyword=Surveil; amount=2 |
| B039 | v8 | bug | FIXED | artifact type=keyword_action; keyword=Discover; amount=10 |
