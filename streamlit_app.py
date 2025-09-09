import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from pathlib import Path
import io

# Page config
st.set_page_config(
    page_title="YouTube Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

class YouTubeAnalyticsApp:
    def __init__(self):
        self.db_path = Path("data/youtube_analytics.sqlite")
        
    def get_database_connection(self):
        """Get database connection"""
        if not self.db_path.exists():
            st.error(f"Database not found at {self.db_path}")
            st.info("Please run the CLI tool first to collect YouTube data.")
            return None
        return sqlite3.connect(self.db_path)
    
    def load_data(self):
        """Load video stats and traffic sources data"""
        conn = self.get_database_connection()
        if conn is None:
            return None, None
        
        try:
            # Load video stats (excluding records marked for exclusion)
            video_query = """
                SELECT 
                    video_id, title, show, episode_num, view_count, 
                    upload_time, visibility, is_short, thumbnail_url
                FROM video_stats 
                WHERE exclude_from_stats = 0
                AND show IS NOT NULL 
                AND episode_num IS NOT NULL
                ORDER BY show, episode_num
            """
            videos_df = pd.read_sql_query(video_query, conn)
            
            # Load traffic sources
            traffic_query = """
                SELECT ts.video_id, ts.traffic_source, ts.views
                FROM traffic_sources ts
                INNER JOIN video_stats vs ON ts.video_id = vs.video_id
                WHERE vs.exclude_from_stats = 0
                AND vs.show IS NOT NULL 
                AND vs.episode_num IS NOT NULL
            """
            traffic_df = pd.read_sql_query(traffic_query, conn)
            
            return videos_df, traffic_df
            
        except Exception as e:
            st.error(f"Error loading data: {e}")
            return None, None
        finally:
            conn.close()
    
    def create_controls(self, videos_df, traffic_df):
        """Create sidebar controls"""
        st.sidebar.header("📊 Filters")
        
        # Show selector
        shows = sorted(videos_df['show'].unique())
        selected_show = st.sidebar.selectbox(
            "Select Show:",
            options=shows,
            index=0 if shows else None
        )
        
        # Filter data by selected show
        show_data = videos_df[videos_df['show'] == selected_show]
        
        if show_data.empty:
            st.sidebar.warning("No data available for selected show")
            return None, None, None, None
        
        # Episode range filter with default to exclude latest episode
        min_episode = int(show_data['episode_num'].min())
        max_episode = int(show_data['episode_num'].max())
        
        # Set default end range to latest - 1 (excluding most recent episode)
        default_end = max(min_episode, max_episode - 1)
        
        episode_range = st.sidebar.slider(
            "Episode Range:",
            min_value=min_episode,
            max_value=max_episode,
            value=(min_episode, default_end),
            step=1,
            help="Default excludes latest episode (data may be incomplete)"
        )
        
        # Filter by episode range
        episode_filtered_data = show_data[
            (show_data['episode_num'] >= episode_range[0]) & 
            (show_data['episode_num'] <= episode_range[1])
        ]
        
        # Traffic source filter
        show_video_ids = episode_filtered_data['video_id'].unique()
        show_traffic_data = traffic_df[traffic_df['video_id'].isin(show_video_ids)]
        
        if not show_traffic_data.empty:
            available_sources = sorted(show_traffic_data['traffic_source'].unique())
            selected_sources = st.sidebar.multiselect(
                "Traffic Sources:",
                options=available_sources,
                default=available_sources,
                help="Select traffic sources to include in analysis"
            )
        else:
            selected_sources = []
        
        return selected_show, episode_range, episode_filtered_data, selected_sources
    
    def prepare_traffic_data(self, filtered_videos, traffic_df, selected_sources=None):
        """Prepare traffic source data for visualization"""
        if filtered_videos.empty or traffic_df.empty:
            return pd.DataFrame()
        
        # Merge video data with traffic sources
        merged_data = filtered_videos.merge(
            traffic_df, 
            on='video_id', 
            how='left'
        )
        
        # Fill missing traffic sources with 'Direct' and 0 views
        merged_data['traffic_source'] = merged_data['traffic_source'].fillna('Direct')
        merged_data['views'] = merged_data['views'].fillna(0)
        
        # Filter by selected traffic sources
        if selected_sources:
            merged_data = merged_data[merged_data['traffic_source'].isin(selected_sources)]
        
        # Group by episode and traffic source
        traffic_summary = merged_data.groupby(['episode_num', 'traffic_source'])['views'].sum().reset_index()
        
        return traffic_summary
    
    def create_visualization(self, filtered_videos, traffic_summary):
        """Create the main visualization"""
        if filtered_videos.empty:
            st.warning("No data to display for the selected filters.")
            return
        
        # Create subplots
        fig = make_subplots(
            rows=1, cols=1,
            subplot_titles=["Views by Episode with Traffic Source Breakdown"]
        )
        
        # Get unique traffic sources and assign colors
        traffic_sources = traffic_summary['traffic_source'].unique()
        colors = px.colors.qualitative.Set3[:len(traffic_sources)]
        
        # Create stacked bar chart for traffic sources
        for i, source in enumerate(traffic_sources):
            source_data = traffic_summary[traffic_summary['traffic_source'] == source]
            
            fig.add_trace(
                go.Bar(
                    x=source_data['episode_num'],
                    y=source_data['views'],
                    name=source,
                    marker_color=colors[i % len(colors)],
                    hovertemplate=f"<b>{source}</b><br>" +
                                "Episode: %{x}<br>" +
                                "Views: %{y:,}<br>" +
                                "<extra></extra>"
                ),
                row=1, col=1
            )
        
        # Calculate 7-day rolling average of total views
        total_views_by_episode = filtered_videos.groupby('episode_num')['view_count'].sum().reset_index()
        total_views_by_episode = total_views_by_episode.sort_values('episode_num')
        
        # Calculate rolling average
        window_size = min(7, len(total_views_by_episode))
        if window_size > 1:
            total_views_by_episode['rolling_avg'] = (
                total_views_by_episode['view_count']
                .rolling(window=window_size, center=True, min_periods=1)
                .mean()
            )
            
            # Add rolling average line
            fig.add_trace(
                go.Scatter(
                    x=total_views_by_episode['episode_num'],
                    y=total_views_by_episode['rolling_avg'],
                    mode='lines',
                    name='7-Day Rolling Average',
                    line=dict(color='red', width=3, dash='dash'),
                    hovertemplate="<b>7-Day Rolling Average</b><br>" +
                                "Episode: %{x}<br>" +
                                "Avg Views: %{y:,.0f}<br>" +
                                "<extra></extra>"
                ),
                row=1, col=1
            )
        
        # Update layout
        fig.update_layout(
            title="Views Analysis by Episode",
            xaxis_title="Episode Number",
            yaxis_title="Views",
            barmode='stack',
            hovermode='x unified',
            height=600,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Update axes
        fig.update_xaxes(tickmode='linear', dtick=1)
        fig.update_yaxes(tickformat=',')
        
        st.plotly_chart(fig, use_container_width=True)
    
    def create_summary_metrics(self, filtered_videos, traffic_summary):
        """Create summary metrics cards"""
        if filtered_videos.empty:
            return
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_episodes = len(filtered_videos)
            st.metric("Total Episodes", f"{total_episodes:,}")
        
        with col2:
            total_views = filtered_videos['view_count'].sum()
            st.metric("Total Views", f"{total_views:,}")
        
        with col3:
            avg_views = filtered_videos['view_count'].mean()
            st.metric("Average Views", f"{avg_views:,.0f}")
        
        with col4:
            if len(filtered_videos) > 1:
                latest_views = filtered_videos.iloc[-1]['view_count']
                previous_views = filtered_videos.iloc[-2]['view_count']
                growth = ((latest_views - previous_views) / previous_views) * 100
                st.metric("Latest Episode Growth", f"{growth:+.1f}%")
    
    def export_to_csv(self, filtered_videos, traffic_summary, selected_show):
        """Create CSV export functionality"""
        if filtered_videos.empty:
            return
        
        st.subheader("📥 Export Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Export video data
            csv_videos = filtered_videos.to_csv(index=False)
            st.download_button(
                label="📊 Download Video Data (CSV)",
                data=csv_videos,
                file_name=f"{selected_show}_video_data.csv",
                mime="text/csv"
            )
        
        with col2:
            # Export traffic source data
            if not traffic_summary.empty:
                csv_traffic = traffic_summary.to_csv(index=False)
                st.download_button(
                    label="🚦 Download Traffic Data (CSV)",
                    data=csv_traffic,
                    file_name=f"{selected_show}_traffic_data.csv",
                    mime="text/csv"
                )
    
    def run(self):
        """Main app runner"""
        # Header
        st.title("📊 YouTube Analytics Dashboard")
        st.markdown("Analyze your YouTube channel performance with interactive visualizations.")
        
        # Load data
        with st.spinner("Loading data..."):
            videos_df, traffic_df = self.load_data()
        
        if videos_df is None or videos_df.empty:
            st.warning("No video data available. Please run the CLI tool to collect YouTube data first.")
            return
        
        # Create controls
        selected_show, episode_range, filtered_videos, selected_sources = self.create_controls(videos_df, traffic_df)
        
        if filtered_videos is None or filtered_videos.empty:
            return
        
        # Prepare traffic data
        traffic_summary = self.prepare_traffic_data(filtered_videos, traffic_df, selected_sources)
        
        # Show summary metrics
        self.create_summary_metrics(filtered_videos, traffic_summary)
        
        # Create main visualization
        st.subheader(f"📈 {selected_show} - Episodes {episode_range[0]} to {episode_range[1]}")
        self.create_visualization(filtered_videos, traffic_summary)
        
        # Show data table
        with st.expander("📋 View Data Table"):
            st.dataframe(
                filtered_videos[['episode_num', 'title', 'view_count', 'upload_time', 'visibility']],
                use_container_width=True
            )
        
        # Export functionality
        self.export_to_csv(filtered_videos, traffic_summary, selected_show)
        
        # Footer
        st.markdown("---")
        st.markdown(
            "<div style='text-align: center; color: gray;'>"
            "YouTube Analytics Dashboard | Built with Streamlit"
            "</div>",
            unsafe_allow_html=True
        )

# Run the app
if __name__ == "__main__":
    app = YouTubeAnalyticsApp()
    app.run()